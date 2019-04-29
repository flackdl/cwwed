import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ActivatedRoute, Router } from "@angular/router";
import { HttpClient } from "@angular/common/http";
import { Component, OnInit, ViewChild, ElementRef, HostListener } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { FormBuilder, FormControl, FormGroup } from "@angular/forms";
import { debounceTime, mergeMap, tap } from 'rxjs/operators';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import {defaults as defaultControls, FullScreen} from 'ol/control.js';
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
import { InjectionService } from "../../ngx-charts/common/tooltip/injection.service";

const seedrandom = require('seedrandom');
const hexToRgba = require("hex-to-rgba");


@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.scss'],
})
export class PsaComponent implements OnInit {
  public DEMO_NAMED_STORM_ID = 1;
  public MAP_LAYER_OSM_STANDARD = 'osm-standard';
  public MAP_LAYER_STAMEN_TONER = 'stamen-toner';
  public MAP_LAYER_MAPBOX_STREETS = 'mapbox-streets';
  public MAP_LAYER_MAPBOX_SATELLITE = 'mapbox-satellite';
  public MAP_LAYER_MAPBOX_LIGHT = 'mapbox-light';

  public mapLayerOptions = [
    { name: 'OpenStreetMap', value: this.MAP_LAYER_OSM_STANDARD },
    { name: 'MapBox Streets', value: this.MAP_LAYER_MAPBOX_STREETS },
    { name: 'MapBox Light', value: this.MAP_LAYER_MAPBOX_LIGHT },
    { name: 'MapBox Satellite', value: this.MAP_LAYER_MAPBOX_SATELLITE },
    { name: 'Stamen Toner', value: this.MAP_LAYER_STAMEN_TONER },
  ];
  public demoDataURL = "/opendap/PSA_demo/Sandy_DBay/DBay-run_map.nc";
  public isLoading = true;
  public isLoadingMap = true;
  public isLoadingOverlayPopup = false;
  public map: Map;
  public namedStorms: any;
  public psaVariables: any[];
  public psaVariablesData: any[];
  public psaDates: string[] = [];
  public form: FormGroup;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];
  public currentConfidence: Number;
  public mapLayerInput = new FormControl(this.MAP_LAYER_OSM_STANDARD);
  public availableMapLayers: {
    variable: any,
    layer: VectorLayer,
  }[];
  public popupOverlay: Overlay;
  public coordinateGraphData: any[];
  public chartWidth: number;
  public chartHeight: number;
  @ViewChild('popup') popupEl: ElementRef;
  @ViewChild('map') mapEl: ElementRef;

  protected _extentInteraction: ExtentInteraction;
  protected _coordinateGraphDataAll: any[] = [];

  constructor(
    private http: HttpClient,
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private cwwedService: CwwedService,
    private modalService: NgbModal,
    private chartTooltipInjectionService: InjectionService,
  ) {}

  ngOnInit() {
    // override chart tooltip container so it works in fullscreen
    this.chartTooltipInjectionService.setContainerElement(this.mapEl.nativeElement);

    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    // create initial form group
    this.form = this.fb.group({
      opacity: new FormControl(.5),
      variables: new FormControl(),
      date: new FormControl(0),
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
    return this.popupOverlay.getPosition() !== undefined;
  }

  public closeOverlayPopup() {
    this.popupOverlay.setPosition(undefined);
  }

  public getDataUrl(format: string): string {
    return `${this.demoDataURL}.${format}`;
  }

  public xAxisTickFormatting(value: string) {
    const date = new Date(value);
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day}`;
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

  public getWaterColorBarValues(variable: string) {
    // TODO
    return [];
  }

  public hasVariableValueAtCurrentDate(variable: string): boolean {
    // TODO
    return true;
  }

  @HostListener('window:resize', ['$event'])
  protected _setMapWidth() {
    this.chartWidth = this.mapEl.nativeElement.offsetWidth * .5;
  }

  @HostListener('window:resize', ['$event'])
  protected _setMapHeight() {
    const chartWidth = this.mapEl.nativeElement.offsetWidth * .5;
    this.chartHeight = chartWidth / 2.0;
  }

  protected _listenForInputChanges() {

    // update map data opacity
    this.form.get('opacity').valueChanges.subscribe(
      (data) => {
        this.availableMapLayers.forEach((availableLayer) => {
          availableLayer['layer'].setStyle((feature) => {
            return this._getWaterLayerStyle(feature);
          });
        });
        /* TODO - handle "wind" (geo_type=point?) layers
        this.windLayer.setStyle((feature) => {
          return this._getWindLayerStyle(feature);
        });
        */
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

    this.form.get('variables').valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
    ).subscribe(
      (variablesValues) => {

        this._updateCoordinateGraphData();

        this.availableMapLayers.forEach((availableLayer) => {
          // remove layer
          if (!variablesValues[availableLayer['variable']['name']]) {
            this.map.removeLayer(availableLayer['layer']);
          } else {
            // check to see if the layer is already present
            let layerExists = false;
            this.map.getLayers().getArray().forEach((layer) => {
              if (layer === availableLayer['layer']) {
                layerExists = true;
              }
            });
            // layer isn't present so add it
            if (!layerExists) {
              availableLayer['layer'].setSource(this._getVariableVectorSource(availableLayer['variable']));
              this.map.addLayer(availableLayer['layer']);
            }
          }
        })
      }
    );

    /* TODO
    // listen for layer input changes
    this.mapLayerWindInput.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
    ).subscribe(
      (value) => {
        this._updateCoordinateGraphData();
        if (!value) {
          this.map.removeLayer(this.windLayer);
        } else {
          this.windLayer.setSource(this._getWindSource());
          this.map.addLayer(this.windLayer);
        }
      }
    );
    */

    // listen for date input changes
    this.form.get('date').valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
      debounceTime(1000),
    ).subscribe((value) => {

      /* TODO
      // remove all layers first then apply chosen ones
      this.map.removeLayer(this.windLayer);
       */

      let updated = false;

      /* TODO
      if (this.mapLayerWaterLevelMaxInput.value) {
        // NOTE: don't check to see if it has the value at the current date because it's static
        this.waterLevelMaxLayer.setSource(this._getWaterLevelMaxSource());
        this.map.addLayer(this.waterLevelMaxLayer);
        updated = true;
      }
      if (this.mapLayerWindInput.value) {
        if (this.hasVariableValueAtCurrentDate('wind')) {
          this.windLayer.setSource(this._getWindSource());
          this.map.addLayer(this.windLayer);
          updated = true;
        }
      }
      */

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
      url: CwwedService.getPsaVariableGeoUrl(this.DEMO_NAMED_STORM_ID, psaVariable.name, date),
      format: new GeoJSON()
    });
  }

  protected _getWindLayerStyle(feature): Style {
    let icon;

    const speed = feature.get('speed') || 0; // m/s
    const knots = speed * 1.94384;

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

    return new Style({
      image: new Icon({
        rotation: -feature.get('direction'),  // direction is in radians and rotates clockwise
        src: icon,
        opacity: this.form.get('opacity').value,
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
            // TODO - designate (in the db) which variables are enabled by default
            psaVariablesFormGroup.addControl(psaVariable.name, new FormControl(true));
          });
          this.form.setControl('variables', psaVariablesFormGroup);
        }),
      mergeMap((x) => {

        // fetch psa variables data
        return this.cwwedService.fetchPSAVariablesData(this.DEMO_NAMED_STORM_ID).pipe(tap(
          (data: any[]) => {
            this.psaVariablesData = data;

            // filter down to time-series only variables
            let timeSeriesVariables = this.psaVariables.filter((variable) => {
              return variable.data_type == 'time-series';
            }).map((variable) => {
              return variable.name;
            });

            // get a list of all the available dates from the time-series specific data
            let timeSeriesData = data.filter((d) => {
              return _.includes(timeSeriesVariables, d.nsem_psa_variable);
            });

            // map the results
            let datesSet = new Set(timeSeriesData.map((d) => d.date).sort());
            datesSet.forEach((d) => {
              this.psaDates.push(d);
            });
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

  protected _getWaterLayerStyle(feature) {
    return new Style({
      fill: new Fill({
        color: hexToRgba(feature.get('color'), this.form.get('opacity').value),
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
      return {
        variable: variable,
        layer: new VectorLayer({
          source: this._getVariableVectorSource(variable),
          style: (feature) => {
            return this._getWaterLayerStyle(feature);
          },
        })
      }
    });

    let zoom = 8;
    let center = fromLonLat(<any>[-75.249730, 39.153332]);

    if (this.route.snapshot.queryParams['zoom']) {
      zoom = this.route.snapshot.queryParams['zoom'];
    }
    if (this.route.snapshot.queryParams['center']) {
      let centerParams = this.route.snapshot.queryParams['center'].map((coord) => {
        return parseFloat(coord);
      });
      center = fromLonLat(centerParams);
    }

    this.map = new Map({
      controls: defaultControls().extend([
        new FullScreen(),
      ]),
      layers: [
        new TileLayer({
          mapName: this.MAP_LAYER_OSM_STANDARD,
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
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_STREETS,
          visible: false,
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
        // TODO - dynamically include specific variables (ie. designated in the db)
        ...this.availableMapLayers.map((l) => { return l.layer;}),
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
      // reset the map's dimensions
      this._setMapHeight();
      this._setMapWidth();
    });

    this.map.on('moveend', (event: any) => {
      const zoom = this.map.getView().getZoom();
      const center = toLonLat(this.map.getView().getCenter());

      // update the url params when the map zooms or moves
      this.router.navigate([], {
        queryParams: {
          zoom: zoom,
          center: center,
        }
      });

      this._updateWindBarbDensity();
    });

    this.map.on('singleclick', (event) => {
      // configure graph overlay
      this._configureGraphOverlay(event);
    });

    this._configureMapExtentInteraction();

    this._configureFeatureHover();

  }

  protected _updateWindBarbDensity() {
    const zoom = this.map.getView().getZoom();

    /* TODO update wind specific layers ?
    // update the wind barb density depending on zoom level
    // NOTE: no style means it's hidden
    this.windLayer.getSource().getFeatures().forEach((feature, i) => {
      feature.setStyle(this._getWindLayerStyle(feature));
      let shouldHide = false;
      if (zoom <= 5 && i % 2 === 0) {
        shouldHide = true;
      } else if (zoom <= 6 && i % 3 === 0) {
        shouldHide = true;
      } else if (zoom <= 7 && i % 4 === 0) {
        shouldHide = true;
      } else if (zoom <= 8 && i % 5 === 0) {
        shouldHide = true;
      } else if (zoom <= 9 && i % 6 === 0) {
        shouldHide = true;
      }
      if (shouldHide) {
        feature.setStyle(new Style());
      }
    });
    */
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
          // include all feature's details but don't overwrite an existing value from an overlapping feature of the same variable

          // wind
          if (!_.has(currentFeature, 'direction') && feature.get('direction') !== undefined) {
            currentFeature['direction'] = feature.get('direction');
          }
          if (!_.has(currentFeature, 'speed') && feature.get('speed') !== undefined) {
            currentFeature['speed'] = feature.get('speed');
          }

          // wave height
          if (feature.get('variable') == 'hs' && !_.has(currentFeature, 'wave_height')) {
            currentFeature['wave_height'] = feature.get('title');
          }

          // water level
          if (feature.get('variable') == 'zeta' && !_.has(currentFeature, 'water_level')) {
            currentFeature['water_level'] = feature.get('title');
          }

          // water level max
          if (feature.get('variable') == 'zeta_max' && !_.has(currentFeature, 'water_level_max')) {
            currentFeature['water_level_max'] = feature.get('title');
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

    const latLon = toLonLat(event.coordinate).reverse();

    this.cwwedService.fetchPSACoordinateData(latLon).subscribe(
      (data: any) => {
        this.isLoadingOverlayPopup = false;

        this._coordinateGraphDataAll = [
          {
            name: 'Water Level (m)',
            series: _.zip(data.dates, data.water_level).map((dateVal) => {
              return {
                name: dateVal[0],
                value: dateVal[1],
              }
            })
          },
          {
            name: 'Wave Height (m)',
            series: _.zip(data.dates, data.wave_height).map((dateVal) => {
              return {
                name: dateVal[0],
                value: dateVal[1],
              }
            })
          },
          {
            name: 'Wind Speed (m/s)',
            series: _.zip(data.dates, data.wind_speed).map((dateVal) => {
              return {
                name: dateVal[0],
                value: dateVal[1],
              }
            })
          },
        ];

        this._updateCoordinateGraphData();
      },
      (error) => {
        console.error(error);
        this.isLoadingOverlayPopup = false;
      }
    );
  }

  protected _updateCoordinateGraphData() {

    const coordinateGraphData = [];
    let data;

    /* TODO
    if (this.mapLayerWindInput.value) {
      data = this._coordinateGraphDataAll.filter((data) => {
        return data.name === 'Wind Speed (m/s)';
      });
      if (data.length) {
        coordinateGraphData.push(data[0]);
      }
    }
    */

    this.coordinateGraphData = coordinateGraphData;
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
