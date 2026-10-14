// Major agricultural-region cities, used for the map and the spray-window picker.
export type City = { side: "l" | "r"; id: string; name: string; urdu: string; lat: number; lon: number; note: string };

export const CITIES: City[] = [
  { side: "l", id: "peshawar", name: "Peshawar", urdu: "پشاور", lat: 34.01, lon: 71.52, note: "Khyber Pakhtunkhwa: wheat, maize, tobacco" },
  { side: "r", id: "islamabad", name: "Islamabad", urdu: "اسلام آباد", lat: 33.68, lon: 73.05, note: "Potohar plateau" },
  { side: "r", id: "lahore", name: "Lahore", urdu: "لاہور", lat: 31.52, lon: 74.36, note: "Punjab: wheat, rice" },
  { side: "l", id: "faisalabad", name: "Faisalabad", urdu: "فیصل آباد", lat: 31.42, lon: 73.08, note: "Punjab: wheat, cotton" },
  { side: "r", id: "multan", name: "Multan", urdu: "ملتان", lat: 30.2, lon: 71.47, note: "South Punjab: cotton, mango" },
  { side: "r", id: "quetta", name: "Quetta", urdu: "کوئٹہ", lat: 30.18, lon: 66.99, note: "Balochistan: orchards" },
  { side: "r", id: "hyderabad", name: "Hyderabad", urdu: "حیدرآباد", lat: 25.39, lon: 68.37, note: "Sindh: sugarcane, cotton" },
  { side: "l", id: "karachi", name: "Karachi", urdu: "کراچی", lat: 24.86, lon: 67.0, note: "Sindh coast" },
];

export const cityById = (id: string | null) => CITIES.find((c) => c.id === id);
