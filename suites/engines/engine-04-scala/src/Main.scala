// engine-04-scala — Tier B (A7), seed 20261022.
// Compilado pelo scalac 2.13.15 REAL (jars do Maven Central) e dexado com
// d8 junto da scala-library: os strings scala.runtime.* ficam no DEX.
package dev.apktester.engine.engine04scala

object Main {
  private final val Seed = 20261022

  // xorshift32 espelha o gerador dos geradores deterministicos do repo.
  def xorshift32(x0: Long): Long = {
    var x = x0 & 0xffffffffL
    x ^= x << 13
    x ^= x >>> 17
    x ^= x << 5
    x & 0xffffffffL
  }

  def checksum(seed: Long, rounds: Int): Long = {
    var x = seed & 0xffffffffL
    var i = 0
    while (i < rounds) {
      x = xorshift32(x)
      i += 1
    }
    x
  }

  def main(args: Array[String]): Unit = {
    val series = (0 until 8).toList.map(i => checksum(Seed + i, 16))
    val line = "engine-04-scala seed=" + Seed + " scala=" + series.mkString(",")
    println(line)
  }
}
