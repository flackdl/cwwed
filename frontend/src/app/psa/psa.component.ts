import { ActivatedRoute, Router } from "@angular/router";
import { HttpClient } from "@angular/common/http";
import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { FormBuilder, FormControl, FormGroup } from "@angular/forms";
import { debounceTime, tap } from 'rxjs/operators';
import { ajax } from 'rxjs/ajax';
import Point from 'ol/geom/Point';
import WKT from 'ol/format/WKT';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import { defaults as defaultControls, FullScreen } from 'ol/control.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat, toLonLat } from 'ol/proj.js';
import ExtentInteraction from 'ol/interaction/Extent.js';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer.js';
import { OSM, XYZ, Vector as VectorSource } from 'ol/source.js';
import { Stroke, Fill, Style, Icon } from 'ol/style.js';
import Overlay from 'ol/Overlay.js';
import * as _ from 'lodash';
import * as Geocoder from "ol-geocoder/dist/ol-geocoder.js";
import { DecimalPipe } from "@angular/common";
import { ChartOptions } from 'chart.js';
import { ToastrService } from 'ngx-toastr';
import { GoogleAnalyticsService } from '../google-analytics.service';
import { Subscription } from "rxjs";

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
  public MAP_LAYER_OSM_STANDARD = 'osm-standard';
  public MAP_LAYER_STAMEN_TONER = 'stamen-toner';
  public MAP_LAYER_MAPBOX_STREETS = 'mapbox-streets';
  public MAP_LAYER_MAPBOX_SATELLITE = 'mapbox-satellite';
  public MAP_LAYER_MAPBOX_LIGHT = 'mapbox-light';

  public DEFAULT_ZOOM_LEVEL = 8;

  public mapLayerOptions = [
    {name: 'OpenStreetMap', value: this.MAP_LAYER_OSM_STANDARD},
    {name: 'MapBox Streets', value: this.MAP_LAYER_MAPBOX_STREETS},
    {name: 'MapBox Light', value: this.MAP_LAYER_MAPBOX_LIGHT},
    {name: 'MapBox Satellite', value: this.MAP_LAYER_MAPBOX_SATELLITE},
    {name: 'Stamen Toner', value: this.MAP_LAYER_STAMEN_TONER},
  ];
  public isLoading = true;
  public isLoadingMap = true;
  public isLoadingOverlayPopup = false;
  public map: Map;
  public namedStorm: any;
  public nsemPsa: any;
  public psaVariables: any[];
  public psaDatesFormatted: string[];  // ng2-charts has a performance issue with accessing these dynamically
  public form: FormGroup;
  public currentFeature: any;
  public currentConfidence: Number;
  public mapLayerInput = new FormControl(this.MAP_LAYER_MAPBOX_STREETS);
  public availableMapLayers: {
    variable: any,
    layer: VectorLayer,
    isLoading: boolean,
  }[];
  public popupOverlay: Overlay;
  public tooltipOverlay: Overlay;
  public lineChartData: any[] = [];
  public lineChartColors: any[] = [];
  public lineChartOptions: ChartOptions;
  public lineChartExportURL: string;
  public initError: string;

  @ViewChild('popup', {static: false}) popupEl: ElementRef;
  @ViewChild('tooltip', {static: false}) tooltipEl: ElementRef;
  @ViewChild('map', {static: false}) mapEl: ElementRef;

  protected _extentInteraction: ExtentInteraction;
  protected _lineChartDataAll: any[] = [];
  protected _windBarbRequest: Subscription;

  constructor(
    private http: HttpClient,
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private decimalPipe: DecimalPipe,
    private cwwedService: CwwedService,
    private toastr: ToastrService,
    private googleAnalyticsService: GoogleAnalyticsService,
  ) {
  }

  ngOnInit() {

    this.namedStorm = _.find(this.cwwedService.namedStorms, (storm) => {
      return this.route.snapshot.params['id'] == storm.id;
    });

    if (this.namedStorm) {

      this.nsemPsa = _.find(this.cwwedService.nsemPsaList, (nsemPsa) => {
        return nsemPsa.named_storm === this.namedStorm.id;
      });

      if (this.nsemPsa) {

        this.psaDatesFormatted = this.nsemPsa.dates.map((date) => {
          return moment(date, moment.defaultFormatUtc).format('YYYY-MM-DD HH:mm');
        });

        // create initial form group
        this.form = this.fb.group({
          opacity: new FormControl(.5),
          variables: new FormControl(),
          date: new FormControl(this.route.snapshot.queryParams['date'] || 0),
        });

        this._fetchDataAndBuildMap();

      } else {
        // no valid psa
        this.isLoading = false;
        this.initError = `No valid PSA found for storm ${this.namedStorm.name}`;
      }
    } else {
      // unknown storm
      this.isLoading = false;
      this.initError = `Unknown storm`;
    }
  }

  public getDateInputFormatted(dateIndex: number) {
    return this.nsemPsa.dates[dateIndex];
  }

  public getDateMin() {
    return this.getDateInputFormatted(0);
  }

  public getDateMax() {
    return this.getDateInputFormatted(this.getDateInputMax());
  }

  public getDateInputMax() {
    return this.nsemPsa.dates.length - 1;
  }

  public getDateCurrent() {
    return this.getDateInputFormatted(this.form.get('date').value || 0);
  }

  public isOverlayVisible(): boolean {
    return this.popupOverlay ? this.popupOverlay.getPosition() !== undefined : false;
  }

  public closeOverlayPopup() {
    this.popupOverlay.setPosition(undefined);
  }

  public getOpenDapUrl(): string {
    const psa = _.find(this.cwwedService.nsemPsaList, (nsemPsa) => {
      return nsemPsa.named_storm === this.namedStorm.id;
    });
    return psa ? psa.opendap_url : '';
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

  public isExtentActive(): boolean {
    return Boolean(this._extentInteraction && this._extentInteraction.getActive());
  }

  public getExtentCoords() {
    const extentCoords = this._extentInteraction.getExtent();
    if (extentCoords) {
      return toLonLat(<any>[extentCoords[0], extentCoords[1]]).concat(
        toLonLat(<any>[extentCoords[2], extentCoords[3]]));
    }
  }

  public disableExtentInteraction() {

    // reset extent selection and captured coordinates
    if (this._extentInteraction) {
      this.map.removeInteraction(this._extentInteraction);
    }

    // reconfigure extent
    this._configureMapExtentInteraction();
  }

  public enableBoxSelection() {
    // track event
    this.googleAnalyticsService.psaBoxSelection(this.namedStorm.name);
    this._extentInteraction.setActive(true);
  }

  public getColorBarVariables() {
    return this.psaVariables.filter((variable) => {
      return variable.geo_type === 'polygon' && variable.data_type === 'time-series';
    });
  }

  public toggleFullscreen(psaContainer: HTMLElement) {
    if (this.isFullscreen()) {
      document.exitFullscreen();
    }
    psaContainer.requestFullscreen();
    // track event
    this.googleAnalyticsService.psaFullScreen(this.namedStorm.name);
  }

  public isFullscreen(): boolean {
    return Boolean(document['fullscreenElement']);
  }

  public isLoadingVariable(psaVariable) {
    const variableLayer = this.availableMapLayers.find((variableLayer) => {
      return variableLayer['variable'].name === psaVariable.name;
    });
    if (!variableLayer) {
      return false;
    }
    // return if it's enabled and still loading
    return this.isVariableDisplayed(psaVariable.name) ? variableLayer.isLoading : false;
  }

  public isVariableDisplayed(variableName: string): boolean {
    return this.form.get('variables').value[variableName];
  }

  protected _listenForInputChanges() {

    // update map data opacity
    this.form.get('opacity').valueChanges.pipe(
      tap((value) => {
        // track event
        this.googleAnalyticsService.psaOpacity(this.namedStorm.name, value);
      })
    ).subscribe(
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
    this.mapLayerInput.valueChanges.pipe(
      tap((value) => {
        // track event
        this.googleAnalyticsService.psaBaseMap(this.namedStorm.name, value);
      })
    ).subscribe(
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
        // track event
        this.googleAnalyticsService.psaVariableToggle(this.namedStorm.name);
      }),
    ).subscribe(
      (variablesValues) => {

        this._updateLineChart();

        this.availableMapLayers.forEach((availableLayer) => {
          // variable toggled off so remove layer from map & available layers
          if (!variablesValues[availableLayer['variable']['name']]) {
            // verify it's populated before trying to remove it
            if (availableLayer['layer']) {
              this._removeVariableVectorLayer(availableLayer)
            }
          } else {  // variable toggled on
            // layer isn't present so add it
            if (!availableLayer['layer']) {
              this._addVariableVectorLayer(availableLayer)
            }
          }
        })
      }
    );

    // listen for date input changes
    this.form.get('date').valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
        // track event
        this.googleAnalyticsService.psaDate(this.namedStorm.name);
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
          updated = true;
          mapLayer.isLoading = true;
          mapLayer.layer.setSource(this._getVariableVectorSource(mapLayer.variable));
          this.map.addLayer(mapLayer.layer);
        }
      });

      // manually toggle that we're not loading anymore since nothing was actually updated (the map handles actual render events)
      if (!updated) {
        this.isLoadingMap = false;
      }
    });
  }

  protected _addVariableVectorLayer(availableLayer) {
    availableLayer['layer'] = new VectorLayer({
      style: (feature) => {
        return availableLayer['variable']['geo_type'] === 'wind-barb' ? this._getWindBarbLayerStyle(feature) : this._getContourLayerStyle(feature);
      },
      source: this._getVariableVectorSource(availableLayer['variable']),
    });
    this.map.addLayer(availableLayer['layer']);
  }

  protected _removeVariableVectorLayer(availableLayer) {
    this.map.removeLayer(availableLayer['layer']);
    delete availableLayer['layer'];
  }

  protected _refreshWindBarbs() {
    const variableLayer = this.availableMapLayers.find((variableLayer) => {
      return variableLayer['variable'].geo_type == 'wind-barb';
    });
    // wind barbs are enabled
    if (variableLayer && this.form.get('variables').value['wind_direction']) {
      // cancel any existing wind barb request
      if (this._windBarbRequest) {
        this._windBarbRequest.unsubscribe();
      }
      variableLayer.isLoading = true;
      // remove and add the layer
      this._removeVariableVectorLayer(variableLayer);
      this._addVariableVectorLayer(variableLayer);
    }
  }

  protected _getVariableVectorSource(psaVariable: any): VectorSource {
    // only time-series variables have dates
    let date = psaVariable.data_type === 'time-series' ? this.getDateInputFormatted(this.form.get('date').value) : null;
    const isWindBarbSource = psaVariable.geo_type === 'wind-barb';
    let url;

    // special handling for wind barbs
    if (isWindBarbSource) {
      // query the density of wind barb points depending on zoom level
      const centerCoords = this.map ? toLonLat(this.map.getView().getCenter()) : this._getDefaultCenter();
      const center = new Point(centerCoords);
      const centerWKT = new WKT().writeGeometry(center);
      const zoom = this.map ? this.map.getView().getZoom() : this._getDefaultZoom();
      let step = 1;
      if (zoom <= 11) {
        step = 10;
      }
      url = CwwedService.getPsaVariableWindBarbsUrl(this.namedStorm.id, psaVariable.name, date, centerWKT, step);
    } else {
      url = CwwedService.getPsaVariableGeoUrl(this.namedStorm.id, this.nsemPsa.id, psaVariable.name, date);
    }

    const format = new GeoJSON();

    const vectorSource = new VectorSource({
      url: url,
      format: format,
      // custom loader to handle errors
      loader: (extent, resolution, projection) => {
        const request: Subscription = ajax.getJSON(url).subscribe(
          (data) => {
            const features = format.readFeatures(data, {featureProjection: projection});
            vectorSource.addFeatures(features);
          },
          (error) => {
            console.error(error);
            this.toastr.error('An unknown error occurred loading map layer');
            vectorSource.removeLoadedExtent(extent);
            this.isLoadingMap = false;
          }
        );
        // save the subscription for wind-barbs to cancel it while the user is zooming/panning around
        if (isWindBarbSource) {
          this._windBarbRequest = request;
        }
      },
    });

    // listen for layer ready
    let sourceListener = vectorSource.on('change', () => {
      if (vectorSource.getState() == 'ready') {
        const variableLayer = this.availableMapLayers.find((variableLayer) => {
          return variableLayer['variable'].name === psaVariable.name;
        });
        if (variableLayer) {
          variableLayer.isLoading = false;
        }
        vectorSource.un('change', sourceListener);
      }
    });

    return vectorSource;
  }

  protected _getWindBarbLayerStyle(feature): Style {
    let icon;
    const zoom = this.map.getView().getZoom();
    const knots = (feature.get('wind_speed_value') || 0) * 1.94384;

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

    const direction = feature.get('wind_direction_value') || {};

    let scale = 1;
    if (zoom >= 13) {
      scale = 1;
    } else if (zoom >= 12 && zoom < 13) {
      scale = .7;
    } else if (zoom >= 11 && zoom < 12) {
      scale = .6;
    } else if (zoom >= 10 && zoom < 11) {
      scale = .5;
    } else if (zoom >= 9 && zoom < 10) {
      scale = .4;
    } else if (zoom >= 8 && zoom < 9) {
      scale = .2;
    } else if (zoom < 8) {
      scale = .1;
    }

    return new Style({
      image: new Icon({
        rotation: -(direction * Math.PI / 180),  // unit is degrees but expects radians; rotates clockwise
        src: icon,
        opacity: this.form.get('opacity').value,
        scale: scale,
      }),
    });
  }

  protected _fetchDataAndBuildMap() {

    // fetch psa variables
    this.cwwedService.fetchPSAVariables(this.namedStorm.id).pipe(
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
    ).subscribe(
      (data) => {
        // build the map
        this._buildMap();
        this._listenForInputChanges();
      },
      (error) => {
        this.toastr.error('An unknown error occurred fetching data variables');
        console.error(error);
        this.isLoading = false;
      });
  }

  protected _getContourLayerStyle(feature) {
    return new Style({
      fill: new Fill({
        color: hexToRgba(feature.get('fill'), this.form.get('opacity').value),
      }),
      stroke: new Stroke({
        color: hexToRgba('#ffffff',  this.form.get('opacity').value),
        size: .3,
      })
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
        isLoading: true,
      }
    });

    let zoom = this._getDefaultZoom();
    let center = this._getDefaultCenter();

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
      controls: defaultControls().extend([
        new FullScreen(),
      ]),
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

    this.tooltipOverlay = new Overlay({
      element: this.tooltipEl.nativeElement,
      offset: [10, 0],
      positioning: 'bottom-left'
    });
    this.map.addOverlay(this.tooltipOverlay);

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
    this.map.on('rendercomplete', (x) => {
      this.isLoadingMap = false;
    });

    this.map.on('moveend', (event: any) => {
      this._updateNavigationURL();
      this._refreshWindBarbs();
    });

    this.map.on('singleclick', (event) => {
      if (!this.isExtentActive()) {
        // configure graph overlay
        this._configureGraphOverlay(event);
        // track event in google analytics
        this.googleAnalyticsService.psaTimeSeries(this.namedStorm.name);
      }
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
      if ((this.popupOverlay && this.popupOverlay.rendered.visible) || this.isExtentActive()) {
        return;
      }

      this.currentConfidence = this._getConfidenceValueAtPixel(event.pixel);

      const currentFeature = {};
      const features = this.map.getFeaturesAtPixel(event.pixel);

      if (features) {
        features.forEach((feature) => {

          const variableName = feature.get('name');
          const variableDataType = feature.get('data_type');
          // append 'Max' if it's a max-values type
          const variableDisplayName = `${feature.get('display_name')} ${variableDataType === 'max-values' ? ' (Max)' : ''}`;
          const variableValue = this.decimalPipe.transform(feature.get('value'), '1.0-2');
          const variableUnits = feature.get('units');

          // find feature's matching psa variable
          const psaVariable = _.find(this.psaVariables, (variable) => {
            return variable.name === variableName;
          });

          if (psaVariable) {
            // special handling for wind barbs
            if (psaVariable.geo_type === 'wind-barb') {
              const variableWindSpeed = feature.get('wind_speed_value');
              const variableWindSpeedUnits = feature.get('wind_speed_units');
              const variableWindDirection = feature.get('wind_direction_value');
              const variableWindDirectionUnits = feature.get('wind_direction_units');
              if (variableWindDirection) {
                currentFeature['Wind Direction'] = `${this.decimalPipe.transform(variableWindDirection, '1.0-2')} ${variableWindDirectionUnits}`;
              }
              // only show the wind barb's speed if the regular wind_speed variable isn't already displayed
              if (!this.isVariableDisplayed('wind_speed') && variableWindSpeed) {
                currentFeature['Wind Speed'] = `${this.decimalPipe.transform(variableWindSpeed, '1.0-2')} ${variableWindSpeedUnits}`;
              }
            } else {
              currentFeature[variableDisplayName] = `${variableValue} ${variableUnits}`;
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

      this.tooltipOverlay.setPosition(event.coordinate);

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

    this.lineChartExportURL = `${this.cwwedService.getPSATimeSeriesDataURL(this.namedStorm.id, latLon[1], latLon[0])}?export=csv`;

    this.cwwedService.fetchPSATimeSeriesData(this.namedStorm.id, latLon[1], latLon[0]).subscribe(
      (data: any) => {
        this.isLoadingOverlayPopup = false;
        this._lineChartDataAll = _.map(data, (variableData: any) => {
          const variable = variableData.variable;
          return {
            label: variable.display_name,
            data: variableData.values,
            yAxisID: variable.element_type,
            variable: variable,  // include actual variable for later comparison against form variables
          };
        });

        this._updateLineChart();
      },
      (error) => {
        console.error(error);
        this.toastr.error('An unknown error occurred fetching graph data');
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
              labelString: 'Water Level / Wave Height (m)',
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

    this.lineChartData = lineChartData;
  }

  protected _configureMapExtentInteraction() {

    // configure box extent selection
    this._extentInteraction = new ExtentInteraction();
    this._extentInteraction.setActive(false);

    // add to map
    this.map.addInteraction(this._extentInteraction);
  }

  protected _getDefaultZoom() {
    return this.DEFAULT_ZOOM_LEVEL;
  }
  protected _getDefaultCenter() {
    return fromLonLat(<any>this.namedStorm.center_coords);
  }
}
