/* Static datasets for the Prompt Caching explainer.
 *
 * Everything here is frozen reference data: section metadata, the toy BPE
 * vocabulary, the worked attention example, the hand-tuned word embeddings, and
 * the canned demo scripts. Colours are expressed as shared-token names so the
 * canvas demos can resolve them per-theme at draw time.
 */

export const SECTIONS = [
  { id: "sec-intro", label: "Intro" },
  { id: "sec-loop", label: "The Loop" },
  { id: "sec-tokenizer", label: "Tokenizer" },
  { id: "sec-embedding", label: "Embedding" },
  { id: "sec-attention", label: "Attention" },
  { id: "sec-kvcache", label: "KV Cache" },
  { id: "sec-providers", label: "Providers" },
  { id: "sec-calculator", label: "Calculator" },
  { id: "sec-summary", label: "Summary" }
];

/* Tier 1: whole words any real tokenizer keeps intact (very high frequency). */
export const WHOLE_TOKENS = new Set([
  "the", "a", "an", "and", "or", "but", "if", "in", "on", "at", "to", "for", "of", "is", "it",
  "that", "was", "are", "be", "this", "have", "from", "with", "as", "by", "not", "what", "all",
  "were", "we", "when", "your", "can", "said", "there", "use", "each", "which", "she", "he",
  "do", "how", "their", "will", "up", "other", "about", "out", "many", "then", "them", "these",
  "so", "some", "her", "would", "make", "like", "has", "him", "into", "time", "very", "could",
  "no", "my", "more", "its", "than", "been", "who", "did", "get", "may", "you", "know", "just",
  "also", "now", "new", "way", "any", "day", "most", "part", "long", "made", "after", "our",
  "two", "much", "too", "us", "end", "does", "such", "where", "why", "here", "old", "big",
  "own", "say", "back", "see", "still", "men", "came", "well", "both", "got", "find", "help",
  "tell", "one", "man", "off", "let", "put", "set", "top", "per", "his", "ask", "try", "run",
  "yet", "far", "hot", "low", "key", "add", "ago", "bad", "bit", "box", "car", "cup", "dry",
  "eat", "eye", "fly", "fun", "gas", "guy", "hit", "ice", "job", "kid", "law", "lot", "map",
  "nor", "odd", "oil", "pay", "ran", "raw", "red", "sat", "six", "sky", "son", "sun", "ten",
  "tip", "war", "win", "yes", "air", "arm", "art", "bag", "bar", "bed", "bus", "cat", "dog",
  "ear", "egg", "fat", "fit", "gap", "hat", "jam", "joy", "lay", "leg", "lip", "log", "mad",
  "mix", "mud", "net", "nut", "pan", "pet", "pie", "pin", "pit", "pot", "rug", "sea", "sir",
  "sum", "tap", "tea", "tie", "tin", "toe", "toy", "van", "via", "wet", "won", "zoo",
  "I", "me", "go", "am", "oh", "OK", "hi", "Mr", "Ms", "Dr", "AI",
  "data", "code", "file", "text", "word", "list", "type", "name", "show", "case", "even",
  "give", "look", "come", "take", "over", "good", "last", "great", "right", "only",
  "work", "first", "call", "keep", "must", "same", "turn", "hand", "high", "head", "start",
  "might", "every", "think", "point", "should", "home", "being", "under", "never", "while",
  "world", "play", "live", "real", "left", "away", "house", "next", "door", "best", "open",
  "kind", "need", "team", "city", "area", "game", "power", "money", "change", "order",
  "group", "place", "since", "second", "late", "hard", "line", "state", "move", "thing",
  "body", "stand", "room", "year", "seem", "side", "number", "system", "table", "market",
  "heart", "level", "court", "clear", "model", "rate", "party", "strong", "often", "story",
  "today", "watch", "carry", "class", "month", "south", "north", "main", "field", "value",
  "form", "land", "local", "small", "cover", "whole", "close", "final", "short", "build",
  "reach", "music", "check", "front", "board", "stage", "early", "voice", "young", "less",
  "free", "human", "stock", "basic", "total", "write", "press", "media", "share", "offer",
  "wrong", "force", "cause", "green", "light", "water", "large", "ready", "paper", "below",
  "sound", "price", "major", "plant", "image", "woman", "raise", "child", "study", "drive",
  "claim", "store", "event", "spend", "break", "trade", "range", "issue", "title", "scene",
  "glass", "agree", "apply", "chief", "piece", "block", "chair", "sport", "black", "white",
  "brown", "clean", "agent", "trust", "treat", "scale", "style", "track", "train", "trial",
  "round", "bring", "count", "death", "fight", "input", "teach", "throw", "truth", "catch",
  "brain", "climb", "crime", "dance", "doubt", "drink", "equal", "faith", "error", "giant",
  "horse", "inner", "knife", "laugh", "learn", "match", "metal", "mouth", "nerve", "noise",
  "ocean", "paint", "phone", "pilot", "plain", "print", "prize", "proof", "proud", "queen",
  "quiet", "rapid", "react", "river", "robot", "rough", "royal", "score", "shape", "sharp",
  "shock", "sight", "skill", "sleep", "slide", "smile", "solid", "solve", "stamp", "steal",
  "steam", "steel", "storm", "stuff", "sugar", "super", "sweet", "taste", "thick", "tower",
  "waste", "wheel", "above", "allow", "apart", "begin", "exist", "grass", "heavy", "judge",
  "label", "legal", "limit", "lunch", "minor", "novel", "nurse", "panel", "pitch", "shell",
  "smell", "smoke", "split", "spray", "stone", "sweep", "theme", "upper", "urban", "virus",
  "worth", "youth", "zero", "three",
  "people", "before", "through", "between", "during", "because", "against", "without",
  "another", "become", "around", "always", "already", "actually", "although", "anything",
  "available", "attention", "business", "community", "children", "company", "different",
  "difficult", "decision", "describe", "director", "education", "everyone", "evidence",
  "example", "exercise", "explain", "finally", "financial", "general", "government",
  "hospital", "important", "interest", "language", "material", "military", "national",
  "nothing", "official", "particular", "perhaps", "physical", "platform", "position",
  "possible", "practice", "president", "probably", "problem", "process", "produce",
  "product", "program", "project", "provide", "purpose", "quality", "question",
  "quickly", "recently", "research", "response", "science", "section", "security",
  "serious", "service", "similar", "society", "specific", "strategy", "strength",
  "structure", "suddenly", "suggest", "support", "surface", "teacher", "thought",
  "tonight", "trouble", "various", "version", "village", "western", "whatever",
  "whether", "working", "writing", "yourself", "remember", "together", "building",
  "computer", "morning", "continue", "training", "document", "standard", "complete",
  "increase", "personal", "consider", "industry", "congress", "function", "customer",
  "pressure", "addition", "campaign", "movement", "approach", "analysis", "election",
  "property", "audience", "solution", "software", "progress", "argument", "delivery",
  "academic", "assembly", "exchange", "identify", "minority", "instance", "emphasis",
  "division", "category", "generate", "estimate", "multiple", "sentence", "feedback",
  "negative", "positive", "currency", "somewhat", "powerful", "creative", "chemical",
  "distinct", "superior", "football", "headline", "proposal",
  "Prompt", "prompt", "caching", "cache", "cached", "token", "tokens", "embed",
  "embedding", "matrix", "vector", "attention", "transformer", "neural", "network",
  "layer", "weight", "gradient", "batch", "epoch", "loss", "inference", "predict",
  "output", "parameter", "dimension", "softmax", "multiply", "compute", "calculate",
  "optimize", "latency", "memory", "billion", "million", "How", "What", "When",
  "Where", "Why", "The", "This", "That", "They", "There", "These", "Those"
]);

/* Tier 2: subword pieces, deduped and sorted longest-first for greedy matching. */
export const SUB_PIECES = [
  "straw", "berry", "under", "stand", "inter", "ation", "ition", "ight", "ough",
  "ound", "ther", "ould", "after", "ment", "ness", "ence", "ance", "ture", "able",
  "ible", "ious", "eous", "ular", "ever", "over", "ward", "ling", "self", "like",
  "ship", "work", "back", "down", "land", "wood", "thing", "some", "mark", "book",
  "fore",
  "tion", "less", "ful",
  "ally", "ical", "ster", "erry", "rain", "road",
  "side", "ouse", "lass",
  "ing", "ion", "ity", "ous", "ive", "ent", "ant", "ure", "age", "ize", "ise",
  "ist", "ism", "ary", "ery", "ory", "ble", "ple", "tle", "dle", "gle", "ess",
  "str", "pre", "pro", "con", "com", "dis", "mis", "sub", "per", "tra", "tri",
  "ack", "ick", "ock", "uck", "ank", "ink", "unk", "amp", "imp", "ump",
  "ash", "ish", "ush", "ath", "eth", "ith", "oth", "ade", "ide", "ode", "ude",
  "ake", "ike", "oke", "ale", "ile", "ole", "ame", "ime", "ome", "ane", "ine",
  "one", "ape", "ipe", "ope", "are", "ire", "ore", "ase", "ose", "ate", "ite",
  "ote", "ute", "ave", "ove", "aze", "oze", "ear", "our", "eer",
  "ght", "est", "ast", "ust", "ost", "ind", "und", "ong", "ang", "ung",
  "orm", "urn", "arn", "orn", "ort", "ard", "ord", "ird",
  "eld", "ild", "old", "alf", "elf", "alk", "all", "ill", "oll", "ull", "ell",
  "awn", "own",
  "ber", "cer", "der", "fer", "ger", "ker", "ler", "mer", "ner", "rer",
  "ser", "ter", "ver", "wer", "zer",
  "cal", "dal", "gal", "mal", "nal", "pal", "ral", "sal", "tal", "val",
  "dom", "tom", "bon", "don", "mon", "ton",
  "ck", "ch", "sh", "th", "ph", "wh", "qu", "gh", "ng", "nk",
  "tr", "cr", "gr", "br", "fr", "fl", "bl", "cl", "gl", "pl", "sl",
  "sp", "sk", "sc", "sw", "sm", "sn", "tw", "wr", "kn",
  "al", "el", "il", "ol", "ul", "ar", "er", "ir", "or", "ur",
  "an", "en", "in", "on", "un", "et", "ot", "ut",
  "ad", "ed", "id", "od", "ud", "ab", "eb", "ib", "ob", "ub",
  "ag", "eg", "ig", "og", "ug", "ek", "ik", "ok", "uk",
  "em", "im", "om", "um", "ep", "ip", "op",
  "es", "os", "ax", "ex", "ix", "ox",
  "ay", "ey", "oy",
  "ba", "be", "bi", "bo", "bu", "ca", "ce", "ci", "co", "cu",
  "da", "de", "di", "fa", "fe", "fi", "fo", "fu",
  "ga", "ge", "gi", "gu", "ha", "he", "ho", "hu",
  "ja", "je", "jo", "ju", "ka", "ke", "ki", "ko", "ku",
  "la", "le", "li", "lo", "lu", "ma", "mi", "mu",
  "na", "ne", "ni", "nu", "pa", "pe", "pi", "po", "pu",
  "ra", "ri", "ru", "sa", "se", "si", "su",
  "ta", "te", "ti", "tu", "va", "ve", "vi", "vo",
  "wa", "wi", "wo", "ya", "ye", "yo", "za", "ze", "zi"
].filter((value, index, arr) => arr.indexOf(value) === index).sort((a, b) => b.length - a.length);

/* Worked attention example (4 tokens, 3 dims), all matrices pre-computed. */
export const ATTN_DATA = {
  emb: [[-0.06, 0.13, -0.30], [0.95, -0.49, -0.64], [-0.05, 0.75, 0.65], [0.51, -0.72, 0.98]],
  Q: [[0.15, 0.07, -0.19], [-0.10, 0.79, -0.78], [-0.71, 0.15, 0.64], [-0.56, -0.06, 0.51]],
  Kt: [[-0.21, 0.30, -0.39, 0.96], [0.13, -0.68, 0.36, -0.74], [0.29, -0.03, -0.56, -1.15]],
  scores: [[-0.08, 0.00, 0.08, 0.31], [-0.10, -0.54, 0.76, 0.21], [0.36, -0.33, -0.04, -1.53], [0.26, -0.15, -0.09, -1.08]],
  weights: [[1.00, 0.00, 0.00, 0.00], [0.61, 0.39, 0.00, 0.00], [0.46, 0.23, 0.31, 0.00], [0.38, 0.25, 0.27, 0.10]],
  V: [[-0.12, -0.00, -0.23], [1.46, 0.62, -0.49], [-0.83, -0.04, -0.01], [0.97, 0.18, 0.78]],
  output: [[-0.12, -0.00, -0.23], [0.50, 0.24, -0.33], [0.02, 0.13, -0.22], [0.20, 0.16, -0.14]]
};

export const AGRID_WORDS = ["the", "cat", "sat", "on"];
export const AGRID_WEIGHTS = [
  [1.00, 0, 0, 0],
  [0.72, 0.28, 0, 0],
  [0.35, 0.41, 0.24, 0],
  [0.18, 0.12, 0.52, 0.18]
];

export const CACHE_TOKENS = ["the", "cat", "sat", "on", "the", "mat"];
export const CACHE_COMPARE_TOKENS = ["the", "cat", "sat", "on", "mat"];

export const INF_RESPONSES = {
  "The meaning of": ["life", "is", "a", "question", "that", "has", "been", "debated", "for", "centuries"],
  "Once upon a": ["time", "there", "was", "a", "small", "village", "near", "the", "edge", "of"],
  default: ["is", "an", "interesting", "topic", "that", "requires", "careful", "thought", "and", "consideration"]
};

export const SMX_TOKENS = ["the", "cat", "sat", "on"];
export const SMX_INITIAL_SCORES = [0.26, -0.15, -0.09, -1.08];

export const CHV_SYSTEM = ["You", "are", "a", "helpful", "AI", "assist", "ant", "."];
export const CHV_QUERIES = [
  ["What", "is", "the", "capital", "of", "France", "?"],
  ["Tell", "me", "about", "prompt", "caching", "."],
  ["What", "is", "the", "meaning", "of", "life", "?"],
  ["Explain", "attention", "in", "transform", "ers", "."],
  ["What", "is", "the", "weather", "today", "?"]
];

export const SUMMARY_STEPS = [
  { title: "Tokenize", tone: "accent", desc: "Text gets chopped into sub-word chunks with deterministic integer IDs." },
  { title: "Embed", tone: "warm", desc: "Each token ID is looked up in a table to become a high-dimensional vector encoding semantic meaning and position." },
  { title: "Compute Q, K, V", tone: "teal", desc: "The attention mechanism multiplies embeddings by three learned weight matrices. Q and K determine relevance, V carries content." },
  { title: "Cache K and V", tone: "indigo", desc: "Save K and V rows so they do not get recomputed when the next token is generated. Only the newest row needs calculating." },
  { title: "Cross-request reuse", tone: "rose", desc: "Providers keep the cache for 5 to 10 minutes. Same prompt prefix on the next request? Reuse everything. 10x cheaper, up to 85% faster." }
];

/* Eight cluster colours, cycled from the shared semantic palette (resolved per
 * theme at draw time). */
export const DIM_COLORS = [
  "--color-amber", "--color-green", "--color-blue", "--color-purple",
  "--color-red", "--color-amber", "--color-purple", "--color-green"
];

/* Pre-built 8-dimensional embeddings for common words. Dimensions loosely map to
 * sentiment, concreteness, animacy, size, formality, action, naturalness,
 * frequency. A teaching tool, not a real model, but hand-tuned to feel realistic. */
export const EMB_VECS = {
  happy: [0.9, 0.3, 0.5, 0.1, 0.2, 0.1, 0.4, 0.8], joyful: [0.95, 0.3, 0.5, 0.1, 0.3, 0.1, 0.4, 0.6],
  glad: [0.85, 0.3, 0.4, 0.1, 0.2, 0.1, 0.4, 0.7], cheerful: [0.88, 0.3, 0.5, 0.2, 0.2, 0.2, 0.4, 0.5],
  delighted: [0.92, 0.3, 0.5, 0.1, 0.4, 0.1, 0.4, 0.4], excited: [0.8, 0.3, 0.6, 0.2, 0.1, 0.6, 0.3, 0.7],
  sad: [-0.8, -0.2, 0.1, -0.1, -0.2, -0.1, -0.3, 0.3], angry: [-0.7, -0.1, 0.2, 0.2, -0.1, 0.6, -0.2, 0.2],
  upset: [-0.6, -0.1, 0.1, 0.1, -0.1, 0.3, -0.2, 0.3], miserable: [-0.9, -0.2, 0.1, -0.1, -0.3, -0.1, -0.3, 0.1],
  depressed: [-0.85, -0.2, 0.1, -0.1, -0.3, 0.0, -0.3, 0.1], furious: [-0.75, -0.1, 0.3, 0.3, -0.1, 0.7, -0.2, 0.1],
  cat: [0.2, 0.9, 0.9, -0.3, 0.0, 0.3, 0.9, 0.9], dog: [0.3, 0.9, 0.9, -0.1, 0.0, 0.4, 0.9, 0.9],
  fish: [0.0, 0.9, 0.9, -0.4, 0.0, 0.3, 0.9, 0.7], bird: [0.1, 0.9, 0.9, -0.3, 0.0, 0.5, 0.9, 0.8],
  horse: [0.1, 0.9, 0.9, 0.5, 0.1, 0.5, 0.9, 0.7], elephant: [0.1, 0.9, 0.9, 0.9, 0.1, 0.3, 0.9, 0.5],
  mouse: [0.0, 0.9, 0.9, -0.7, 0.0, 0.4, 0.9, 0.7], whale: [0.1, 0.9, 0.9, 0.95, 0.1, 0.3, 0.9, 0.4],
  car: [0.0, 0.9, 0.0, 0.3, 0.0, 0.5, -0.5, 0.9], truck: [0.0, 0.9, 0.0, 0.6, -0.1, 0.4, -0.5, 0.7],
  bicycle: [0.1, 0.9, 0.0, -0.2, 0.0, 0.5, -0.3, 0.7], airplane: [0.1, 0.9, 0.0, 0.8, 0.1, 0.6, -0.5, 0.6],
  boat: [0.1, 0.9, 0.0, 0.5, 0.0, 0.4, -0.2, 0.6], submarine: [-0.1, 0.8, 0.0, 0.7, 0.2, 0.3, -0.6, 0.3],
  pizza: [0.4, 0.9, 0.0, -0.1, -0.2, 0.0, 0.2, 0.8], bread: [0.1, 0.9, 0.0, -0.2, 0.0, 0.0, 0.5, 0.9],
  apple: [0.2, 0.9, 0.0, -0.4, 0.0, 0.0, 0.9, 0.9], cake: [0.5, 0.9, 0.0, -0.1, -0.1, 0.0, 0.3, 0.7],
  steak: [0.2, 0.9, 0.0, 0.0, 0.0, 0.0, 0.4, 0.6], sushi: [0.3, 0.9, 0.0, -0.2, 0.2, 0.0, 0.3, 0.5],
  computer: [0.0, 0.7, 0.0, 0.2, 0.3, 0.2, -0.8, 0.8], software: [0.0, 0.2, 0.0, 0.0, 0.4, 0.2, -0.9, 0.7],
  algorithm: [0.0, 0.1, 0.0, 0.0, 0.6, 0.3, -0.9, 0.4], database: [0.0, 0.4, 0.0, 0.1, 0.5, 0.1, -0.9, 0.5],
  robot: [0.0, 0.7, 0.3, 0.2, 0.2, 0.4, -0.8, 0.5], internet: [0.0, 0.2, 0.0, 0.0, 0.3, 0.2, -0.8, 0.8],
  ocean: [0.2, 0.8, 0.0, 0.9, 0.2, 0.2, 0.95, 0.7], mountain: [0.1, 0.9, 0.0, 0.9, 0.2, 0.1, 0.95, 0.7],
  river: [0.1, 0.9, 0.0, 0.5, 0.1, 0.4, 0.95, 0.8], forest: [0.2, 0.9, 0.2, 0.7, 0.1, 0.1, 0.95, 0.7],
  flower: [0.4, 0.9, 0.2, -0.4, 0.1, 0.0, 0.95, 0.7], tree: [0.2, 0.9, 0.2, 0.5, 0.0, 0.0, 0.95, 0.9],
  sun: [0.4, 0.8, 0.0, 0.8, 0.1, 0.1, 0.9, 0.9], moon: [0.1, 0.8, 0.0, 0.5, 0.2, 0.0, 0.9, 0.8],
  red: [0.0, 0.7, 0.0, 0.0, 0.0, 0.0, 0.3, 0.9], blue: [0.0, 0.7, 0.0, 0.0, 0.0, 0.0, 0.3, 0.9],
  green: [0.1, 0.7, 0.0, 0.0, 0.0, 0.0, 0.5, 0.9], black: [-0.1, 0.7, 0.0, 0.0, 0.1, 0.0, 0.2, 0.9],
  white: [0.1, 0.7, 0.0, 0.0, 0.1, 0.0, 0.2, 0.9],
  hand: [0.0, 0.9, 0.8, -0.2, 0.0, 0.5, 0.5, 0.9], head: [0.0, 0.9, 0.8, 0.0, 0.0, 0.2, 0.5, 0.9],
  heart: [0.4, 0.6, 0.8, -0.1, 0.2, 0.3, 0.6, 0.9], eye: [0.0, 0.9, 0.8, -0.3, 0.0, 0.3, 0.5, 0.9],
  love: [0.8, 0.3, 0.5, 0.1, 0.2, 0.2, 0.4, 0.9], hate: [-0.8, -0.2, -0.3, 0.1, -0.1, 0.3, -0.3, 0.2],
  truth: [0.3, 0.0, 0.0, 0.0, 0.6, 0.0, 0.3, 0.7], justice: [0.2, 0.0, 0.0, 0.0, 0.7, 0.2, 0.2, 0.6],
  freedom: [0.5, 0.0, 0.3, 0.0, 0.5, 0.2, 0.3, 0.7], peace: [0.6, 0.0, 0.2, 0.0, 0.4, -0.1, 0.4, 0.7],
  war: [-0.5, 0.3, 0.5, 0.5, 0.3, 0.8, 0.1, 0.8], death: [-0.7, 0.3, 0.5, 0.0, 0.4, 0.0, 0.3, 0.8],
  run: [0.1, 0.5, 0.7, 0.0, -0.1, 0.9, 0.4, 0.9], walk: [0.1, 0.5, 0.7, 0.0, 0.0, 0.6, 0.4, 0.9],
  jump: [0.2, 0.5, 0.7, 0.0, -0.1, 0.9, 0.4, 0.8], swim: [0.2, 0.5, 0.7, 0.0, 0.0, 0.8, 0.5, 0.7],
  eat: [0.2, 0.6, 0.7, 0.0, -0.1, 0.5, 0.4, 0.9], sleep: [0.3, 0.5, 0.7, 0.0, 0.0, -0.2, 0.4, 0.9],
  think: [0.0, 0.1, 0.7, 0.0, 0.3, 0.4, 0.3, 0.9], write: [0.0, 0.4, 0.6, 0.0, 0.3, 0.5, 0.1, 0.8],
  token: [0.0, 0.4, 0.0, -0.1, 0.5, 0.1, -0.7, 0.5], embedding: [0.0, 0.2, 0.0, 0.0, 0.6, 0.1, -0.8, 0.3],
  attention: [0.0, 0.1, 0.3, 0.0, 0.5, 0.3, -0.6, 0.5], transformer: [0.0, 0.3, 0.0, 0.3, 0.5, 0.3, -0.8, 0.4],
  model: [0.0, 0.3, 0.0, 0.1, 0.4, 0.2, -0.5, 0.8], prompt: [0.0, 0.4, 0.0, -0.1, 0.3, 0.2, -0.6, 0.5],
  cache: [0.0, 0.3, 0.0, 0.0, 0.4, 0.1, -0.7, 0.5], matrix: [0.0, 0.3, 0.0, 0.0, 0.5, 0.1, -0.6, 0.4],
  big: [0.0, 0.5, 0.0, 0.8, -0.1, 0.0, 0.3, 0.9], small: [0.0, 0.5, 0.0, -0.8, -0.1, 0.0, 0.3, 0.9],
  huge: [0.0, 0.5, 0.0, 0.9, 0.0, 0.0, 0.3, 0.7], tiny: [0.1, 0.5, 0.0, -0.9, -0.1, 0.0, 0.3, 0.7],
  hot: [0.0, 0.6, 0.0, 0.0, -0.1, 0.0, 0.5, 0.9], cold: [-0.1, 0.6, 0.0, 0.0, 0.0, 0.0, 0.5, 0.9],
  warm: [0.3, 0.6, 0.0, 0.0, 0.0, 0.0, 0.5, 0.8], cool: [0.1, 0.6, 0.0, 0.0, 0.0, 0.0, 0.5, 0.8],
  rain: [0.0, 0.8, 0.0, 0.3, 0.0, 0.2, 0.9, 0.8], snow: [0.1, 0.8, 0.0, 0.3, 0.0, 0.1, 0.9, 0.7],
  doctor: [0.2, 0.6, 0.9, 0.0, 0.6, 0.4, 0.2, 0.7], teacher: [0.3, 0.5, 0.9, 0.0, 0.4, 0.4, 0.2, 0.8],
  engineer: [0.0, 0.5, 0.9, 0.0, 0.5, 0.4, -0.3, 0.6], scientist: [0.1, 0.4, 0.9, 0.0, 0.6, 0.4, 0.0, 0.5],
  king: [0.1, 0.6, 0.9, 0.3, 0.8, 0.2, 0.2, 0.7], queen: [0.1, 0.6, 0.9, 0.2, 0.8, 0.2, 0.2, 0.6],
  man: [0.0, 0.7, 0.9, 0.2, 0.0, 0.3, 0.5, 0.95], woman: [0.0, 0.7, 0.9, 0.1, 0.0, 0.3, 0.5, 0.95]
};

export const EMB_PAIRS = [
  ["happy", "joyful"], ["happy", "sad"], ["happy", "submarine"], ["cat", "dog"],
  ["cat", "computer"], ["king", "queen"], ["man", "woman"], ["ocean", "mountain"],
  ["run", "walk"], ["car", "bicycle"], ["love", "hate"], ["token", "embedding"],
  ["big", "tiny"], ["doctor", "engineer"], ["pizza", "sushi"], ["hot", "cold"]
];

export const EMB_CATEGORIES = {
  Emotions: ["happy", "joyful", "glad", "cheerful", "excited", "sad", "angry", "upset", "miserable", "furious"],
  Animals: ["cat", "dog", "fish", "bird", "horse", "elephant", "mouse", "whale"],
  Vehicles: ["car", "truck", "bicycle", "airplane", "boat", "submarine"],
  Food: ["pizza", "bread", "apple", "cake", "steak", "sushi"],
  Nature: ["ocean", "mountain", "river", "forest", "flower", "tree", "sun", "moon"],
  Tech: ["computer", "software", "algorithm", "database", "robot", "internet"],
  Actions: ["run", "walk", "jump", "swim", "eat", "sleep", "think", "write"],
  LLM: ["token", "embedding", "attention", "transformer", "model", "prompt", "cache", "matrix"],
  Abstract: ["love", "hate", "truth", "justice", "freedom", "peace", "war", "death"],
  People: ["doctor", "teacher", "engineer", "scientist", "king", "queen", "man", "woman"]
};
