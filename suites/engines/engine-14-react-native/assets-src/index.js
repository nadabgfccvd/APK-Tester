// engine-14-react-native — Tier B (A7), seed 20261022.
// Compilado pelo hermesc real (npm react-native@0.76.9) para
// assets/index.android.bundle (bytecode Hermes, magic 0x1F1903C6).
'use strict';

const SEED = 20261022;

function xorshift32(x) {
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  return x >>> 0;
}

function checksum(seed, rounds) {
  let x = seed >>> 0;
  for (let i = 0; i < rounds; i += 1) {
    x = xorshift32(x);
  }
  return x;
}

const series = [];
for (let i = 0; i < 8; i += 1) {
  series.push(checksum(SEED + i, 16));
}

console.log(
  'engine-14-react-native seed=' + SEED + ' hermes=' + series.join(','),
);

module.exports = { checksum, series };
