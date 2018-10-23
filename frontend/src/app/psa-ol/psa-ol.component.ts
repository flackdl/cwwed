import { Component, OnInit } from '@angular/core';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import {platformModifierKeyOnly} from 'ol/events/condition.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat } from 'ol/proj';
import ExtentInteraction from 'ol/interaction/Extent.js';
import {Tile as TileLayer, Vector as VectorLayer} from 'ol/layer.js';
import {OSM, Vector as VectorSource} from 'ol/source.js';
import { Fill, Stroke, Style } from 'ol/style.js';


@Component({
  selector: 'app-psa-ol',
  templateUrl: './psa-ol.component.html',
  styleUrls: ['./psa-ol.component.scss']
})
export class PsaOlComponent implements OnInit {
  public map;

  constructor() { }

  ngOnInit() {

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
    window.addEventListener('keydown', function(event) {
      if (event.keyCode == 16) {
        extent.setActive(true);
      }
    });
    window.addEventListener('keyup', function(event) {
      if (event.keyCode == 16) {
        console.log(extent.getExtent());
        extent.setActive(false);
      }
    });

    this.map.on('pointermove', (event) => {
      const features = this.map.getFeaturesAtPixel(event.pixel);
      if (!features) {
        //info.innerText = '';
        //info.style.opacity = 0;
        return;
      }
      const properties = features[0].getProperties();
      console.log(properties);
      //info.innerText = JSON.stringify(properties, null, 2);
      //info.style.opacity = 1;

    });
  }

}
