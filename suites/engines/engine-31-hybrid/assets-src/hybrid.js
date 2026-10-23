// hybrid.js — engine-31 (TST-14, Tier A, A4): fonte compilada pelo
// hermesc REAL (npm hermes-engine 0.11.0) para assets/index.android.bundle
// (bytecode Hermes, magic 0xC61FBC03).
function hybridProbe(a, b) {
  var engine = "engine-31-hybrid";
  var marker = "apktester-hermes-tst14";
  var h = 20261022;
  var s = engine + ":" + marker + ":" + (a + b);
  for (var i = 0; i < s.length; i++) {
    h = (31 * h + s.charCodeAt(i)) | 0;
  }
  return h;
}
globalThis.__apktesterHybrid = hybridProbe(13, 29);
hybridProbe(1, 2);
