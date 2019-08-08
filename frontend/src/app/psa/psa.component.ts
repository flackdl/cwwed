import { ActivatedRoute, Router } from "@angular/router";
import { HttpClient } from "@angular/common/http";
import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { FormBuilder, FormControl, FormGroup } from "@angular/forms";
import { debounceTime, mergeMap, tap } from 'rxjs/operators';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import { platformModifierKeyOnly } from 'ol/events/condition.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat, toLonLat } from 'ol/proj.js';
import ExtentInteraction from 'ol/interaction/Extent.js';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer.js';
import { OSM, XYZ, Vector as VectorSource } from 'ol/source.js';
import { Fill, Style, Icon } from 'ol/style.js';
import Overlay from 'ol/Overlay.js';
import * as _ from 'lodash';
import * as Geocoder from "ol-geocoder/dist/ol-geocoder.js";
import { DecimalPipe } from "@angular/common";
import { ChartOptions } from 'chart.js';

const moment = require('moment');
const seedrandom = require('seedrandom');
const hexToRgba = require("hex-to-rgba");
const randomColor = require('randomcolor');


@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.scss'],
  providers: [DecimalPipe],
})
export class PsaComponent implements OnInit {
  public DEMO_NAMED_STORM_ID = 1;
  public MAP_LAYER_OSM_STANDARD = 'osm-standard';
  public MAP_LAYER_STAMEN_TONER = 'stamen-toner';
  public MAP_LAYER_MAPBOX_STREETS = 'mapbox-streets';
  public MAP_LAYER_MAPBOX_SATELLITE = 'mapbox-satellite';
  public MAP_LAYER_MAPBOX_LIGHT = 'mapbox-light';

  public mapLayerOptions = [
    {name: 'OpenStreetMap', value: this.MAP_LAYER_OSM_STANDARD},
    {name: 'MapBox Streets', value: this.MAP_LAYER_MAPBOX_STREETS},
    {name: 'MapBox Light', value: this.MAP_LAYER_MAPBOX_LIGHT},
    {name: 'MapBox Satellite', value: this.MAP_LAYER_MAPBOX_SATELLITE},
    {name: 'Stamen Toner', value: this.MAP_LAYER_STAMEN_TONER},
  ];
  public demoDataURL = "/opendap/PSA_demo/sandy.nc";
  public isLoading = true;
  public isLoadingMap = true;
  public isLoadingOverlayPopup = false;
  public map: Map;
  public namedStorm: any;
  public psaVariables: any[];
  public psaDates: string[] = [];
  public psaDatesFormatted: string[] = [];
  public form: FormGroup;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];
  public currentConfidence: Number;
  public mapLayerInput = new FormControl(this.MAP_LAYER_MAPBOX_STREETS);
  public availableMapLayers: {
    variable: any,
    layer: VectorLayer,
  }[];
  public popupOverlay: Overlay;
  public lineChartData: any[] = [];
  public lineChartColors: any[] = [];
  public lineChartOptions: ChartOptions;
  public lineChartExportURL: string;
  @ViewChild('popup') popupEl: ElementRef;
  @ViewChild('map') mapEl: ElementRef;

  protected _extentInteraction: ExtentInteraction;
  protected _lineChartDataAll: any[] = [];

  constructor(
    private http: HttpClient,
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private decimalPipe: DecimalPipe,
    private cwwedService: CwwedService,
  ) {
  }

  ngOnInit() {

    this.nsemList = this.cwwedService.nsemList;
    this.namedStorm = _.find(this.cwwedService.namedStorms, (storm) => {
      return storm.id === this.DEMO_NAMED_STORM_ID;
    });

    // create initial form group
    this.form = this.fb.group({
      opacity: new FormControl(.5),
      variables: new FormControl(),
      date: new FormControl(this.route.snapshot.queryParams['date'] || 0),
    });

    this._fetchDataAndBuildMap();
  }

  public getDateInputFormatted(dateIndex: number) {
    return this.psaDates ? this.psaDates[dateIndex] : '';
  }

  public getDateMin() {
    return this.getDateInputFormatted(0);
  }

  public getDateMax() {
    return this.getDateInputFormatted(this.getDateInputMax());
  }

  public getDateInputMax() {
    return this.psaDates ? this.psaDates.length - 1 : 0;
  }

  public isOverlayVisible(): boolean {
    return this.popupOverlay ? this.popupOverlay.getPosition() !== undefined : false;
  }

  public closeOverlayPopup() {
    this.popupOverlay.setPosition(undefined);
  }

  public getDataUrl(format: string): string {
    return `${this.demoDataURL}.${format}`;
  }

  public timeSeriesVariables() {
    return _.filter(this.psaVariables, (psaVariable) => {
      return psaVariable.data_type === 'time-series' && psaVariable.geo_type == 'polygon';
    });
  }

  public hasTimeSeriesVariablesDisplayed(): boolean {
    let displayedVariables = [];
    let timeSeriesVariables = this.timeSeriesVariables();
    _.each(this.form.get('variables').value, (enabled, name) => {
      if (enabled) {
        let psaVariable = _.find(timeSeriesVariables, (variable) => {
          return variable.name == name;
        });
        if (psaVariable) {
          displayedVariables.push(psaVariable);
        }
      }
    });
    return displayedVariables.length > 0;
  }

  public hasExtentSelection(): boolean {
    return this._extentInteraction && this._extentInteraction.getExtent();
  }

  public resetExtentInteraction() {

    // reset extent selection and captured coordinates
    if (this._extentInteraction) {
      this.map.removeInteraction(this._extentInteraction);
    }
    this.extentCoords = null;

    // reconfigure extent
    this._configureMapExtentInteraction();
  }

  public getColorBarVariables() {
    return this.psaVariables.filter((variable) => {
      return variable.geo_type === 'polygon';
    });
  }

  public getPsaVariableNameFormatted(psaVariable) {
    // remove "maximum" from `max-values` data types
    if (psaVariable.data_type === 'max-values') {
      return psaVariable.name.replace(/ maximum/i, '');
    }
    return psaVariable.name;
  }

  public toggleFullscreen(psaContainer: HTMLElement) {
    if (this.isFullscreen()) {
      document.exitFullscreen();
    }
    psaContainer.requestFullscreen();
  }

  public isFullscreen(): boolean {
    return Boolean(document['fullscreenElement']);
  }

  protected _listenForInputChanges() {

    // update map data opacity
    this.form.get('opacity').valueChanges.subscribe(
      (data) => {

        // update layers
        this.availableMapLayers.forEach((availableLayer) => {
          if (availableLayer['layer']) {
            // wind barbs
            if (availableLayer['variable']['geo_type'] === 'wind-barb') {
              availableLayer['layer'].setStyle((feature) => {
                return this._getWindBarbLayerStyle(feature);
              });
            } else { // water contours
              availableLayer['layer'].setStyle((feature) => {
                return this._getContourLayerStyle(feature);
              });
            }
          }
        });
      }
    );

    // update map tile layer
    this.mapLayerInput.valueChanges.subscribe(
      (value) => {
        this.map.getLayers().getArray().forEach((layer) => {
          const mapName = layer.get('mapName');
          if (mapName) {
            layer.setVisible(mapName === value);
          }
        });
      }
    );

    // listen for variable changes
    this.form.get('variables').valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
    ).subscribe(
      (variablesValues) => {

        this._updateLineChart();

        this.availableMapLayers.forEach((availableLayer) => {
          // variable toggled off so remove layer from map & available layers
          if (!variablesValues[availableLayer['variable']['name']]) {
            // verify it's populated
            if (availableLayer['layer']) {
              this.map.removeLayer(availableLayer['layer']);
              delete availableLayer['layer'];
            }
          } else {  // variable toggled on
            // layer isn't present so add it
            if (!availableLayer['layer']) {
              availableLayer['layer'] = new VectorLayer({
                style: (feature) => {
                  return availableLayer['variable']['geo_type'] === 'wind-barb' ? this._getWindBarbLayerStyle(feature) : this._getContourLayerStyle(feature);
                },
                source: this._getVariableVectorSource(availableLayer['variable']),
              });
              this.map.addLayer(availableLayer['layer']);
            }
          }
        })
      }
    );

    // listen for date input changes
    this.form.get('date').valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
      debounceTime(1000),
    ).subscribe((value) => {

      this._updateNavigationURL();

      // remove all layers first then apply chosen ones
      this.availableMapLayers.forEach((mapLayer) => {
        if (mapLayer.layer) {
          this.map.removeLayer(mapLayer.layer);
        }
      });

      let updated = false;

      this.availableMapLayers.forEach((mapLayer) => {
        if (mapLayer.layer && this.form.get('variables').get(mapLayer.variable.name).value) {
          mapLayer.layer.setSource(this._getVariableVectorSource(mapLayer.variable));
          this.map.addLayer(mapLayer.layer);
          updated = true;
        }
      });

      // manually toggle that we're not loading anymore since nothing was actually updated (the map handles actual render events)
      if (!updated) {
        this.isLoadingMap = false;
      }
    });
  }

  protected _getVariableVectorSource(psaVariable: any): VectorSource {
    // only time-series variables have dates
    let date = psaVariable.data_type === 'time-series' ? this.getDateInputFormatted(this.form.get('date').value) : null;
    return new VectorSource({
      url: CwwedService.getPsaVariableGeoUrl(this.DEMO_NAMED_STORM_ID, psaVariable.id, date),
      format: new GeoJSON()
    });
  }

  protected _getWindBarbLayerStyle(feature): Style {
    const zoom = this.map.getView().getZoom();

    let icon;

    // the speed is stored in the feature's "meta" key
    const meta = feature.get('meta') || {};
    const speedData = meta['speed'] || {};
    const knots = (speedData['value'] || 0) * 1.94384;

    // https://commons.wikimedia.org/wiki/Wind_speed
    if (_.inRange(knots, 0, 2)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_00.svg.png';
    } else if (_.inRange(knots, 2, 7)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_01.svg.png';
    } else if (_.inRange(knots, 7, 12)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_02.svg.png';
    } else if (_.inRange(knots, 12, 17)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_03.svg.png';
    } else if (_.inRange(knots, 17, 22)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_04.svg.png';
    } else if (_.inRange(knots, 22, 27)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_05.svg.png';
    } else if (_.inRange(knots, 27, 32)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_06.svg.png';
    } else if (_.inRange(knots, 32, 37)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_07.svg.png';
    } else if (_.inRange(knots, 37, 42)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_08.svg.png';
    } else if (_.inRange(knots, 42, 47)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_09.svg.png';
    } else if (_.inRange(knots, 47, 52)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_10.svg.png';
    } else if (_.inRange(knots, 52, 57)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_11.svg.png';
    } else if (_.inRange(knots, 57, 62)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_12.svg.png';
    } else if (_.inRange(knots, 62, 83)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_13.svg.png';
    } else if (_.inRange(knots, 83, 102)) {
      icon = '/assets/psa/50px-Symbol_wind_speed_14.svg.png';
    } else {
      icon = '/assets/psa/50px-Symbol_wind_speed_15.svg.png';
    }

    const directionData = meta.direction || {};

    let scale = 1;
    if (zoom === 10) {
      scale = .7;
    } else if (zoom === 9) {
      scale = .5;
    } else if (zoom === 8) {
      scale = .3;
    } else if (zoom <= 7) {
      scale = .15;
    }

    return new Style({
      image: new Icon({
        rotation: -(directionData.value * Math.PI / 180),  // unit is degrees but expects radians, rotates clockwise
        src: icon,
        opacity: this.form.get('opacity').value,
        scale: scale,
      }),
    });
  }

  protected _fetchDataAndBuildMap() {

    // fetch psa variables
    this.cwwedService.fetchPSAVariables(this.DEMO_NAMED_STORM_ID).pipe(
      tap(
        (data: any[]) => {
          this.isLoading = false;
          this.psaVariables = data;

          // create and populate variables form group
          let psaVariablesFormGroup = this.fb.group({});
          this.psaVariables.forEach((psaVariable) => {
            psaVariablesFormGroup.addControl(psaVariable.name, new FormControl(psaVariable.auto_displayed));
          });
          this.form.setControl('variables', psaVariablesFormGroup);
        }),
      mergeMap(() => {
        // fetch psa variables data dates
        return this.cwwedService.fetchPSAVariablesDataDates(this.DEMO_NAMED_STORM_ID).pipe(tap(
          (data: any[]) => {
            this.psaDates = data;
          }
        ));
      }),
    ).subscribe(
      (data) => {
        // build the map
        this._buildMap();
        this._listenForInputChanges();
      },
      (error) => {
        console.error(error);
        this.isLoading = false;
      });
  }

  protected _getContourLayerStyle(feature) {
    return new Style({
      fill: new Fill({
        color: hexToRgba(feature.get('fill'), this.form.get('opacity').value),
      }),
    })
  }

  protected _buildMap() {

    const mapBoxToken = 'pk.eyJ1IjoiZmxhY2thdHRhY2siLCJhIjoiY2l6dGQ2MXp0MDBwMzJ3czM3NGU5NGRsMCJ9.5zKo4ZGEfJFG5ph6QlaDrA';

    // create an overlay to anchor the address specific popup to the map
    this.popupOverlay = new Overlay({
      element: this.popupEl.nativeElement,
      autoPan: true,
      autoPanAnimation: {
        duration: 250
      }
    });

    this.availableMapLayers = this.psaVariables.map((variable) => {
      let layer;
      let source = this._getVariableVectorSource(variable);

      //
      // only populate the layers which are set as "auto displayed"
      //

      // wind barbs are displayed as points vs contours
      if (variable.geo_type === 'wind-barb') {
        if (variable.auto_displayed) {
          layer = new VectorLayer({
            source: source,
            style: (feature) => {
              return this._getWindBarbLayerStyle(feature);
            },
          });
        }
      } else {
        if (variable.auto_displayed) {
          layer = new VectorLayer({
            source: source,
            style: (feature) => {
              return this._getContourLayerStyle(feature);
            },
          });
        }
      }

      return {
        variable: variable,
        layer: layer,
      }
    });

    let zoom = 9;
    let center = fromLonLat(<any>[-74.37052594737246, 39.360018072433775]);

    if (this.route.snapshot.queryParams['zoom']) {
      zoom = parseFloat(this.route.snapshot.queryParams['zoom']) || zoom;
    }
    if (this.route.snapshot.queryParams['center']) {
      let centerParams = this.route.snapshot.queryParams['center'].map((coord) => {
        return parseFloat(coord);
      });
      center = fromLonLat(centerParams);
    }

    this.map = new Map({
      layers: [
        new TileLayer({
          mapName: this.MAP_LAYER_OSM_STANDARD,
          visible: false,
          source: new OSM(),
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_LIGHT,
          visible: false,
          source: new XYZ({
            url: `https://api.mapbox.com/styles/v1/mapbox/light-v9/tiles/256/{z}/{x}/{y}?access_token=${mapBoxToken}`,
          })
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_SATELLITE,
          visible: false,
          source: new XYZ({
            url: `https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v9/tiles/256/{z}/{x}/{y}?access_token=${mapBoxToken}`,
          })
        }),
        // DEFAULT
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_STREETS,
          source: new XYZ({
            url: `https://api.mapbox.com/styles/v1/mapbox/streets-v10/tiles/256/{z}/{x}/{y}?access_token=${mapBoxToken}`,
          })
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_STAMEN_TONER,
          visible: false,
          source: new XYZ({
            url: 'http://a.tile.stamen.com/toner/{z}/{x}/{y}.png',
          })
        }),
        // only include the variable layers that are "auto displayed"
        ...this.availableMapLayers.filter((ml) => {
          return ml.variable.auto_displayed
        }).map((l) => {
          return l.layer;
        }),
      ],
      target: this.mapEl.nativeElement,
      overlays: [this.popupOverlay],
      view: new View({
        center: center,
        zoom: zoom,
      })
    });

    // instantiate geocoder
    const geocoder = new Geocoder('nominatim', {
      provider: 'osm',
      lang: 'en-US',
      placeholder: 'Search ...',
      targetType: 'glass-button',
      limit: 5,
      keepOpen: true,
      autoComplete: true,
      countrycodes: 'us',
    });
    this.map.addControl(geocoder);

    // flag we're finished loading the map
    this.map.on('rendercomplete', () => {
      this.isLoadingMap = false;
    });

    this.map.on('moveend', (event: any) => {
      this._updateNavigationURL();
    });

    this.map.on('singleclick', (event) => {
      // configure graph overlay
      this._configureGraphOverlay(event);
    });

    this._configureMapExtentInteraction();

    this._configureFeatureHover();

  }

  protected _updateNavigationURL() {
    const zoom = this.map.getView().getZoom();
    const center = toLonLat(this.map.getView().getCenter());

    // update the url params when the map zooms or moves
    this.router.navigate([], {
      queryParams: {
        zoom: zoom,
        center: center,
        date: this.form.get('date').value,
      }
    });
  }

  protected _getConfidenceValueAtPixel(pixel) {
    // TODO - generating random confidence using a consistent seed of the current pixel
    const rand = seedrandom(pixel.reduce(
      (p1, p2) => {
        return Math.round(p1) + Math.round(p2);
      }));
    const randValue = Math.round(rand() * 100);
    if (randValue < 50) {
      return randValue + 50;
    } else {
      return randValue;
    }
  }

  protected _configureFeatureHover() {

    // highlight current feature
    this.map.on('pointermove', (event) => {

      // don't show feature details if there's any popup overlay already present
      if (this.popupOverlay && this.popupOverlay.rendered.visible) {
        return;
      }

      this.currentConfidence = this._getConfidenceValueAtPixel(event.pixel);

      const currentFeature = {};
      const features = this.map.getFeaturesAtPixel(event.pixel);

      if (features) {
        features.forEach((feature) => {

          const variableName = feature.get('name');
          const variableValue = this.decimalPipe.transform(feature.get('value'), '1.0-2');
          const variableUnits = feature.get('units');
          const variableMeta = feature.get('meta') || {};

          // find feature's matching psa variable
          const psaVariable = _.find(this.psaVariables, (variable) => {
            return variable.name === variableName;
          });

          if (psaVariable) {
            // special handling for wind barbs
            if (psaVariable.geo_type === 'wind-barb') {
              if (variableMeta['speed'] && variableMeta['direction']) {
                currentFeature['Wind Speed'] = `${this.decimalPipe.transform(variableMeta['speed']['value'], '1.0-2')} ${variableMeta['speed']['units']}`;
                currentFeature['Wind Direction'] = `${this.decimalPipe.transform(variableMeta['direction']['value'], '1.0-2')} ${variableMeta['direction']['units']}`;
              }
            } else {
              currentFeature[variableName] = `${variableValue} ${variableUnits}`;
            }
          }
        });
      }

      if (!_.keys(currentFeature).length) {
        this.currentFeature = undefined;
        return;
      }

      // include the current coordinates
      currentFeature['coordinate'] = toLonLat(event.coordinate).reverse();

      this.currentFeature = currentFeature;
    });
  }

  protected _configureGraphOverlay(event) {
    this.isLoadingOverlayPopup = true;

    // verify there is data at this location
    const features = this.map.getFeaturesAtPixel(event.pixel);
    if (!features) {
      this.closeOverlayPopup();
      this.isLoadingOverlayPopup = false;
      return;
    }

    this.popupOverlay.setPosition(event.coordinate);

    const latLon = toLonLat(event.coordinate);

    this.lineChartExportURL = `${this.cwwedService.getPSATimeSeriesDataURL(this.DEMO_NAMED_STORM_ID, latLon[1], latLon[0])}?export=csv`;

    this.cwwedService.fetchPSATimeSeriesData(this.DEMO_NAMED_STORM_ID, latLon[1], latLon[0]).subscribe(
      (data: any) => {
        this.isLoadingOverlayPopup = false;
        this._lineChartDataAll = _.map(data, (variableData: any) => {
          const variable = variableData.variable;
          return {
            label: variable.name,
            data: variableData.values,
            yAxisID: variable.element_type,
            variable: variable,  // include actual variable for later comparison against form variables
          };
        });

        this._updateLineChart();
      },
      (error) => {
        console.error(error);
        this.isLoadingOverlayPopup = false;
      }
    );
  }

  protected _getColorForVariable(variableName: string, alpha?: number) {
    return randomColor.randomColor({
      luminosity: 'bright',
      seed: variableName,
      alpha: alpha || 1,
      format: 'rgba',
    });
  }

  protected _updateLineChart() {
    const lineChartData = [];

    // include the line chart data if that variable is currently being displayed
    this._lineChartDataAll.forEach((data) => {
      if (this.form.get('variables').value[data.variable.name]) {
        lineChartData.push(data);
      }
    });

    this.lineChartOptions = {
      responsive: true,
      scales: {
        // use an empty structure as a placeholder for dynamic theming
        xAxes: [{}],
        yAxes: [
          {
            id: 'water',
            scaleLabel: {
              display: true,
              labelString: 'Water (m)',
            },
            position: 'left',
          },
          {
            id: 'wind',
            scaleLabel: {
              display: true,
              labelString: 'Wind (m/s)',
            },
            position: 'right',
          },
        ],
      },
    };

    this.lineChartColors = lineChartData.map((data) => {
      const color = this._getColorForVariable(data.variable.name, .5);
      return {
        borderColor: color,
        backgroundColor: color,
        fill: false,
      }
    });

    this.psaDatesFormatted = this.psaDates.map((date) => {
      return moment(date).format('YYYY-MM-DD HH:mm');
    });

    this.lineChartData = lineChartData;
  }

  protected _configureMapExtentInteraction() {

    // configure box extent selection
    this._extentInteraction = new ExtentInteraction({
      condition: platformModifierKeyOnly,
    });
    this.map.addInteraction(this._extentInteraction);
    this._extentInteraction.setActive(false);

    // enable geo box interaction by holding shift
    window.addEventListener('keydown', (event: any) => {
      if (event.keyCode == 16) {
        this._extentInteraction.setActive(true);
      }
    });

    // disable geo box interaction and capture extent box
    window.addEventListener('keyup', (event: any) => {
      if (event.keyCode == 16) {
        const extentCoords = this._extentInteraction.getExtent();
        if (extentCoords && extentCoords.length === 4) {
          this.extentCoords = toLonLat(<any>[extentCoords[0], extentCoords[1]]).concat(
            toLonLat(<any>[extentCoords[2], extentCoords[3]]));
        } else {
          this.extentCoords = null;
        }
        this._extentInteraction.setActive(false);
      }
    });
  }
}
