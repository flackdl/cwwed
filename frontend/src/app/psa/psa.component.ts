import { ActivatedRoute } from "@angular/router";
import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { geoJSON, GeoJSONOptions, latLng, tileLayer } from "leaflet";
import { HttpClient } from "@angular/common/http";
import { GeoJsonObject } from "geojson";

const mbToken = 'pk.eyJ1IjoiZmxhY2thdHRhY2siLCJhIjoiY2l6dGQ2MXp0MDBwMzJ3czM3NGU5NGRsMCJ9.5zKo4ZGEfJFG5ph6QlaDrA';
const mbUrl = 'https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=' + mbToken;

@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.css'],
})
export class PsaComponent implements OnInit {
  public nsemId: number;
  public isLoaded: boolean = false;
  public namedStorms: any;
  public nsemList: any;
  public mapOptions = {
    layers: <any>[
      //tileLayer('http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '...' })
      tileLayer(mbUrl, { id: 'mapbox.streets', maxZoom: 18, attribution: '...' })
    ],
    zoom: 8,
    center: latLng(39.153332, -75.249730)
  };

  private _geoJsonOptions: GeoJSONOptions = {
    onEachFeature: function (feature, layer) {
      layer.bindPopup("Water Depth: " + feature.properties.title + "'");
    },
    style: function (feature) {
      return {
        color: feature.properties.fill,
        fillOpacity: .8
      };
    }
  };

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
    private http: HttpClient,
  ) {}

  ngOnInit() {
    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    this.http.get('https://s3.amazonaws.com/cwwed-static-assets-frontend/contours.geojson').subscribe((data) => {
      this.mapOptions.layers.push(geoJSON(<GeoJsonObject>data, this._geoJsonOptions));
      this.isLoaded = true;
    });

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.nsemId = parseInt(data.id);
      }
    });
  }

  public chooseStorm(storm: any) {
    console.log(storm);
  }

}
