/**
 * ALL remote imagery lives here. Every URL was opened and verified to return HTTP 200 on 2026-10-24.
 * Images are rendered through <SafeImage>, which applies a black-and-white treatment (CSS grayscale + contrast)
 * so every photo fits the brand in both themes, lazy-loads, shows a skeleton while loading, and falls back to a local gradient on error.
 */
const U = (id: string, w = 1600, q = 80) => `https://images.unsplash.com/${id}?w=${w}&q=${q}&auto=format&fit=crop`;
const P = (id: number, w = 1600) => `https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&w=${w}`;

export interface Img { url: string; alt: string; source: string }
const img = (url: string, alt: string, source: string): Img => ({ url, alt, source });

export const IMAGES = {
  hero: {
    // SOURCE: Pexels 14845309 - Mumbai skyline at dusk
    main: img(P(14845309, 2000), "Mumbai skyline at dusk with lit apartment towers", "Pexels"),
    // SOURCE: Unsplash (photo-1551288049-bebda4e38f71) - dark analytics dashboard on a laptop screen
    dashboard: img(U("photo-1551288049-bebda4e38f71", 1800), "Dark analytics dashboard on a laptop screen", "Unsplash"),
    // SOURCE: Pexels 16952108 - India Gate silhouetted at sunset, New Delhi
    city: img(P(16952108, 1800), "India Gate in New Delhi silhouetted against a sunset sky", "Pexels"),
    // SOURCE: Unsplash (photo-1451187580459-43490279c0fa) - Earth at night with city light networks
    network: img(U("photo-1451187580459-43490279c0fa", 1800), "Earth at night with glowing city networks", "Unsplash"),
  },
  features: {
    // SOURCE: Unsplash (photo-1526628953301-3e589a6a8b74) - dashboard tiles with line charts
    metrics: img(U("photo-1526628953301-3e589a6a8b74", 1200), "Dashboard tiles showing metric line charts", "Unsplash"),
    // SOURCE: Unsplash (photo-1558494949-ef010cbdcc31) - data center server racks
    datasets: img(U("photo-1558494949-ef010cbdcc31", 1200), "Data center server racks with network cables", "Unsplash"),
    // SOURCE: Unsplash (photo-1535378917042-10a22c95931a) - friendly humanoid robot, used for TARA
    tara: img(U("photo-1535378917042-10a22c95931a", 1200), "Humanoid robot representing the TARA AI assistant", "Unsplash"),
    // SOURCE: Unsplash (photo-1512758017271-d7b84c2113f1) - planning board with sticky notes
    conflicts: img(U("photo-1512758017271-d7b84c2113f1", 1200), "Planning board covered in sticky notes", "Unsplash"),
    // SOURCE: Unsplash (photo-1550751827-4bd374c3f58b) - glowing circuit schematic
    formula: img(U("photo-1550751827-4bd374c3f58b", 1200), "Glowing circuit schematic on a dark screen", "Unsplash"),
    // SOURCE: Unsplash (photo-1639322537228-f710d846310a) - connected blocks network
    versions: img(U("photo-1639322537228-f710d846310a", 1200), "Connected blocks representing an immutable version chain", "Unsplash"),
    // SOURCE: Pexels 669615 - printed charts and notebook on a desk
    reports: img(P(669615, 1200), "Printed charts and a notebook on a dark desk", "Pexels"),
    // SOURCE: Pexels 265087 - laptop with bar and pie charts
    dashboards: img(P(265087, 1200), "Laptop displaying bar and pie charts", "Pexels"),
  },
  auth: {
    // SOURCE: Pexels 14845309 - Mumbai skyline at dusk
    login: img(P(14845309, 1600), "Mumbai skyline at dusk", "Pexels"),
    // SOURCE: Pexels 12903045 - aerial view of Chennai
    register: img(P(12903045, 1600), "Aerial view of Chennai city", "Pexels"),
    // SOURCE: Pexels 11321242 - Charminar, Hyderabad
    forgot: img(P(11321242, 1600), "Charminar monument in Hyderabad", "Pexels"),
  },
  about: {
    // SOURCE: Pexels 31968829 - group of young Indian professionals
    team: img(P(31968829, 1600), "Group of young colleagues smiling together", "Pexels"),
    // SOURCE: Pexels 1181676 - software engineer at a dual-monitor workstation
    workspace: img(P(1181676, 1600), "Software engineer working at a dual-monitor workstation", "Pexels"),
    // SOURCE: Pexels 3183150 - overhead view of people collaborating at a table
    collaboration: img(P(3183150, 1600), "Overhead view of colleagues collaborating at a wooden table", "Pexels"),
    // SOURCE: Pexels 14094276 - Red Fort, Delhi
    office: img(P(14094276, 1600), "The Red Fort in Delhi under a pale sky", "Pexels"),
    // SOURCE: Unsplash (photo-1553877522-43269d4ea984) - person working on a laptop
    laptop: img(U("photo-1553877522-43269d4ea984", 1600), "Person working at a laptop in a bright office", "Unsplash"),
    // SOURCE: Pexels 13369323 - busy street market in India
    market: img(P(13369323, 1600), "Busy street market with shops and scooters in India", "Pexels"),
  },
  emptyStates: {
    // SOURCE: Unsplash (photo-1432888498266-38ffec3eaf0a) - tidy desk from above
    generic: img(U("photo-1432888498266-38ffec3eaf0a", 900, 75), "Tidy desk with notebooks seen from above", "Unsplash"),
    // SOURCE: Unsplash (photo-1531297484001-80022131f5a1) - laptop glowing in the dark
    data: img(U("photo-1531297484001-80022131f5a1", 900, 75), "Laptop glowing softly in a dark room", "Unsplash"),
    // SOURCE: Unsplash (photo-1494438639946-1ebd1d20bf85) - minimal lamp against a pale wall
    quiet: img(U("photo-1494438639946-1ebd1d20bf85", 900, 75), "Minimal lamp against a pale wall", "Unsplash"),
  },
  avatars: {
    // SOURCE: Pexels portraits 31112232, 11800909, 29820147, 12310724, 15126949, 13339844
    a: img(P(31112232, 160), "Portrait of a woman working at a desk", "Pexels"),
    b: img(P(11800909, 160), "Portrait of a bearded man", "Pexels"),
    c: img(P(29820147, 160), "Portrait of a woman in a shawl", "Pexels"),
    d: img(P(12310724, 160), "Portrait of a man in a blazer outdoors", "Pexels"),
    e: img(P(15126949, 160), "Portrait of a man in a dark suit", "Pexels"),
    f: img(P(13339844, 160), "Portrait of a man in a white shirt", "Pexels"),
  },
  templates: {
    // SOURCE: Pexels 13612713 - colourful spice market (retail / sales)
    sales: img(P(13612713, 800), "Colourful spices and grains on display at a market", "Pexels"),
    // SOURCE: Unsplash (photo-1554224155-6726b3ff858f) - finance documents and calculator
    finance: img(U("photo-1554224155-6726b3ff858f", 800, 75), "Finance documents with a calculator", "Unsplash"),
    // SOURCE: Pexels 12419503 - supermarket shelves of packaged foods (operations / supply)
    operations: img(P(12419503, 800), "Supermarket shelves stocked with packaged foods", "Pexels"),
  },
  backgrounds: {
    // SOURCE: Unsplash (photo-1558591710-4b4a1ae0f04d) - white abstract waves
    waves: img(U("photo-1558591710-4b4a1ae0f04d", 1600, 70), "Abstract white waves", "Unsplash"),
    // SOURCE: Unsplash (photo-1518770660439-4636190af475) - circuit board macro
    circuit: img(U("photo-1518770660439-4636190af475", 1600, 70), "Macro photo of a circuit board", "Unsplash"),
    // SOURCE: Unsplash (photo-1526374965328-7f61d4dc18c5) - falling green code
    code: img(U("photo-1526374965328-7f61d4dc18c5", 1600, 70), "Cascading code characters on a dark screen", "Unsplash"),
    // SOURCE: Pexels 160087 - Mumbai skyline at sunset
    towers: img(P(160087, 1600), "Mumbai skyline at sunset across the Arabian Sea", "Pexels"),
  },
} as const;
