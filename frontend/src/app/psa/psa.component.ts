import { ActivatedRoute } from "@angular/router";
import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { HttpClient } from "@angular/common/http";

import Map from 'ol/Map.js';
import View from 'ol/View.js';
import { platformModifierKeyOnly } from 'ol/events/condition.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat, toLonLat } from 'ol/proj.js';
import ExtentInteraction from 'ol/interaction/Extent.js';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer.js';
import { OSM, Vector as VectorSource } from 'ol/source.js';
import { Fill, Style } from 'ol/style.js';

@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.scss'],
})
export class PsaComponent implements OnInit {
  public map;
  public nsemId: number;
  public namedStorms: any;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
    private http: HttpClient,
  ) {}

  ngOnInit() {
    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    this._buildMap();

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.nsemId = parseInt(data.id);
      }
    });
  }

  protected _buildMap() {

    const vectorSource = new VectorSource({
      url: 'https://s3.amazonaws.com/cwwed-static-assets-frontend/contours.geojson',
      format: new GeoJSON()
    });

    this.map = new Map({
      layers: [
        new TileLayer({
          source: new OSM()
        }),
        new VectorLayer({
          source: vectorSource,
          style: (feature) => {
            return new Style({
              fill: new Fill({
                color: feature.get('fill')
              })
            })
          },
        })
      ],
      target: 'map',
      view: new View({
        center: fromLonLat([-75.249730, 39.153332]),
        zoom: 8,
      })
    });

    const extent = new ExtentInteraction({
      condition: platformModifierKeyOnly
    });
    this.map.addInteraction(extent);
    extent.setActive(false);

    // Enable interaction by holding shift
    window.addEventListener('keydown', (event: any) => {
      if (event.keyCode == 16) {
        this.extentCoords = [];
        extent.setActive(true);
      }
    });

    window.addEventListener('keyup', (event: any) => {
      if (event.keyCode == 16) {
        const extentCoords = extent.getExtent();
        if (extentCoords && extentCoords.length === 4) {
            this.extentCoords = toLonLat([extentCoords[0], extentCoords[1]]).concat(
              toLonLat([extentCoords[2], extentCoords[3]]));
            console.log(this.extentCoords);
        }
        //this.extentCoords = toLonLat([extentCoords[0], extentCoords[1]]);
        extent.setActive(false);
      }
    });

    this.map.on('pointermove', (event) => {
      const features = this.map.getFeaturesAtPixel(event.pixel);
      if (!features) {
        this.currentFeature = undefined;
        return;
      }
      this.currentFeature = features[0].getProperties();
    });

  }

}
