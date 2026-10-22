export interface Position {
  latitude: number;
  longitude: number;
}

export interface Service {
  language: string;
  startTime: string;
  date: string;
}

export interface Church {
  id: string;
  name: string;
  website: string;
  position: Position;
  religion: string;
  denomination: string;
  services: Service[];
}

export interface Filters {
  query: string;
  date: string | null;
  language: string;
}

export interface Result {
  church: Church;
  services: Service[];
  distanceKm: number | null;
}
