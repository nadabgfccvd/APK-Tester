//! native.zig — engine-12 (Tier A, A4): zig cc -target x86_64-linux-android
//! -shared -fPIC -O2 -nostdlib (freestanding: o zig 0.13 não fornece bionic;
//! código sem chamadas de libc — mesmo assim é um ELF Android real).
export fn apktester_probe() c_int {
    var h: c_int = 20261022;
    const engine = "engine-12-zig";
    const marker = "apktester-zig-native";
    for (engine) |ch| {
        h = 31 * h + @as(c_int, ch);
    }
    for (marker) |ch| {
        h = 31 * h + @as(c_int, ch);
    }
    return h;
}

comptime {
    _ = apktester_probe;
}
