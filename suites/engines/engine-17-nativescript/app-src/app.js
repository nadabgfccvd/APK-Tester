// engine-17-nativescript — Tier B (A7), seed 20261022.
// app JS raiz executado pelo runtime libNativeScript.so real
// (@nativescript/android@8.8.2) a partir de assets/app/.
'use strict';

var SEED = 20261022;

function xorshift32(x) {
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  return x >>> 0;
}

function checksum(seed, rounds) {
  var x = seed >>> 0;
  var i;
  for (i = 0; i < rounds; i += 1) {
    x = xorshift32(x);
  }
  return x;
}

console.log('engine-17-nativescript seed=' + SEED +
  ' runtime=' + checksum(SEED, 16));
