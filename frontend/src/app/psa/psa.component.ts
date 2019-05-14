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
import { DecimalPipe } from "@angular/common";

const seedrandom = require('seedrandom');
const hexToRgba = require("hex-to-rgba");


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
    private decimalPipe: DecimalPipe,
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

  public getSelectedDate() {
    return this.getDateInputFormatted(this.form.get('date').value);
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

        // update layers
        this.availableMapLayers.forEach((availableLayer) => {
          // wind barbs
          if (availableLayer['variable']['geo_type'] === 'wind-arrow') {
            availableLayer['layer'].setStyle((feature) => {
              return this._getWindLayerStyle(feature);
            });
          } else { // water contours
            availableLayer['layer'].setStyle((feature) => {
              return this._getWaterLayerStyle(feature);
            });
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

    // listen for date input changes
    this.form.get('date').valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
      debounceTime(1000),
    ).subscribe((value) => {

      // remove all layers first then apply chosen ones
      this.availableMapLayers.forEach((mapLayer) => {
        this.map.removeLayer(mapLayer.layer);
      });

      let updated = false;

      this.availableMapLayers.forEach((mapLayer) => {
        if (this.form.get('variables').get(mapLayer.variable.name).value) {
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
      url: CwwedService.getPsaVariableGeoUrl(this.DEMO_NAMED_STORM_ID, psaVariable.name, date),
      format: new GeoJSON()
    });
  }

  protected _getWindLayerStyle(feature): Style {

    const icon = '/assets/psa/arrow.png';

    return new Style({
      image: new Icon({
        rotation: -feature.get('value'),  // direction is in radians and rotates clockwise
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
      let layer;

      if (variable.geo_type === 'wind-arrow') {
        layer = new VectorLayer({
          source: this._getVariableVectorSource(variable),
          style: (feature) => {
            return this._getWindLayerStyle(feature);
          },
        })
      } else {
        layer = new VectorLayer({
          source: this._getVariableVectorSource(variable),
          style: (feature) => {
            return this._getWaterLayerStyle(feature);
          },
        })
      }

      return {
        variable: variable,
        layer: layer,
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
    });

    this.map.on('singleclick', (event) => {
      // configure graph overlay
      this._configureGraphOverlay(event);
    });

    this._configureMapExtentInteraction();

    this._configureFeatureHover();

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
          const variableUnit = feature.get('unit');

          // make sure not to overwrite an existing value from an overlapping feature of the same variable
          if (variableName !== undefined && !_.has(currentFeature, variableName)) {
            currentFeature[variableName] = `${variableValue} ${variableUnit}`;
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

    this.cwwedService.fetchPSACoordinateData(this.DEMO_NAMED_STORM_ID, latLon).subscribe(
      (data: any) => {
        this.isLoadingOverlayPopup = false;
        this._coordinateGraphDataAll = _.map(data, (variableData, variableName) => {
          return {
            name: variableName,
            series: _.zip(data.dates, variableData).map((dateVal) => {
              return {
                name: dateVal[0],
                value: dateVal[1],
              }
            })
          };
        });

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

    // include the coordinate variable data if that variable is currently being displayed
    this._coordinateGraphDataAll.forEach((data) => {
      if (this.form.get('variables').value[data.name]) {
        coordinateGraphData.push(data);
      }
    });

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
