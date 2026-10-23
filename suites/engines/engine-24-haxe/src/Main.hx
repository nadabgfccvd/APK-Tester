// Main.hx — engine-24 (Tier A, A4): Haxe 4.3 target -java (hxjava + ant).
// O compilador gera fontes Java sob o pacote haxe.root e executa o javac
// (via hxjava/ant); as classes haxe.root.* entram no DEX (contrato).
package;

class Main {
    public static inline var ENGINE:String = "engine-24-haxe";
    public static inline var MARKER:String = "haxe.root";
    public static inline var SEED:Int = 20261022;

    public static function probe():String {
        var parts:Array<String> = [ENGINE, MARKER, Std.string(SEED)];
        return parts.join(":");
    }

    public static function checksum():Int {
        var h:Int = SEED;
        var s:String = probe();
        for (i in 0...s.length) {
            h = 31 * h + s.charCodeAt(i);
        }
        return h;
    }

    static function main() {
        trace(probe());
    }
}
