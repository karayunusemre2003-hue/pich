// Render an SVG (or any NSImage-readable file) to a transparent PNG of a given height.
// usage: svg2png IN.svg OUT.png HEIGHT
import AppKit
let a = CommandLine.arguments
guard a.count == 4, let img = NSImage(contentsOfFile: a[1]), let h = Double(a[3]), img.size.height > 0 else {
    FileHandle.standardError.write("usage: svg2png IN OUT HEIGHT (unreadable input?)\n".data(using: .utf8)!); exit(2)
}
let w = (img.size.width * h / img.size.height).rounded()
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(w), pixelsHigh: Int(h), bitsPerSample: 8, samplesPerPixel: 4,
                           hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
img.draw(in: NSRect(x: 0, y: 0, width: w, height: h))
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[2]))
