/**
 * Illustrative, pre-split examples. Different BPE vocabularies may segment
 * the same text differently, so these arrays teach patterns rather than claim
 * to be output from a specific production tokenizer.
 */
export const tokenExamples = [
  {
    label: "Everyday English",
    description: "Frequent English words often stay together as useful chunks.",
    text: "Coffee tastes better outside.",
    tokens: ["Coffee", " tastes", " better", " outside", "."]
  },
  {
    label: "A subword seam",
    description: "A familiar word such as unhappiness can split into reusable pieces.",
    text: "unhappiness can grow.",
    tokens: ["un", "happiness", " can", " grow", "."]
  },
  {
    label: "Emoji and Japanese",
    description: "Emoji, modifiers, and non-English text can use many smaller fragments.",
    text: "Hi 👋🏽, こんにちは!",
    tokens: ["Hi", " ", "👋", "🏽", ",", " ", "こ", "ん", "に", "ち", "は", "!"]
  },
  {
    label: "A long number",
    description: "Long digit strings often break at odd-looking chunk boundaries.",
    text: "Invoice 123456789012345 is due.",
    tokens: ["Invoice", " ", "123", "456", "789", "012", "345", " is", " due", "."]
  }
];

/**
 * Count user-visible Unicode characters rather than UTF-16 code units.
 *
 * @param {string} text
 * @returns {number}
 */
export function characterCount(text) {
  return Array.from(text).length;
}

/**
 * Return display counts for one pre-split example.
 *
 * @param {{ text: string, tokens: string[] }} example
 * @returns {{ tokenCount: number, characterCount: number }}
 */
export function getTokenExampleStats(example) {
  return {
    tokenCount: example.tokens.length,
    characterCount: characterCount(example.text)
  };
}

/**
 * Show leading spaces with middle dots while preserving the rest of a token.
 *
 * @param {string} token
 * @param {boolean} showWhitespace
 * @returns {string}
 */
export function formatTokenForDisplay(token, showWhitespace) {
  if (!showWhitespace) {
    return token;
  }
  return token.replace(/^ +/, (spaces) => "·".repeat(spaces.length));
}
