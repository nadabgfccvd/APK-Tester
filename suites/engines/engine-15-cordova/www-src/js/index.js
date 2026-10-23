// engine-15-cordova — Tier B (A7), seed 20261022.
// www do fixture; cordova.js e cordova_plugins.js entram pelo template
// real do cordova-android@14.0.1 e pelo formato canonico do prepare.
'use strict';

var SEED = 20261022;

function xorshift32(x) {
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  return x >>> 0;
}

document.addEventListener('deviceready', function () {
  var el = document.getElementById('probe');
  var x = SEED >>> 0;
  for (var i = 0; i < 16; i += 1) {
    x = xorshift32(x);
  }
  if (el) {
    el.textContent = 'deviceready ok, checksum=' + x;
  }
}, false);
