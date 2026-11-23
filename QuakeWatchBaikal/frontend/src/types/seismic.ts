export interface Earthquake {
  id: number;
  datetime_utc: string;
  latitude: number;
  longitude: number;
  depth: number;
  energy_class: number;
  region: string;
}

export interface FilterParams {
  start_date: string;
  end_date: string;
  min_energy_class: number;
}

export interface PolarizationResult {
  station: string;
  eq_time: string;
  is_synthetic: boolean;
  timeline: string[];
  azimuth: (number | null)[];
  incidence_angle: (number | null)[];
  rectilinearity: number[];
  ellipticity: number[];
  tides: number[];
  stats: {
    bg_az: number | null;
    bg_inc: number | null;
    pre_az: number | null;
    pre_inc: number | null;
    diff_az: number | null;
  };
  ray_params: {
    azimuth: number;
    incidence: number;
  };
  beachball_png: string | null;
}
