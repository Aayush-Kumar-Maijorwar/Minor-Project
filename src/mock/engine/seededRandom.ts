

// We implement a simple LCG or use mulberry32 for seeded randoms
// Since npm package mulberry32 might not be a direct export or standard,
// let's implement a simple seeded random to avoid dependency issues if it's not a standard package.
// Actually, mulberry32 is usually a simple 32-bit PRNG algorithm.

export function createSeededRandom(seed: number) {
  return function() {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  }
}

export function generateSeed(patientId: string, modalities: string[]): number {
  let str = patientId + [...modalities].sort().join(',');
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash >>> 0;
}
