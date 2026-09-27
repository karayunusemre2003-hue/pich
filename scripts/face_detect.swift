// macOS Vision face detector for qa_reel.py.
// usage: face_detect IMG... -> JSON {"img": [[x, y, w, h], ...]} normalized, top-left origin.
import Foundation
import Vision
import AppKit

var out: [String: [[Double]]] = [:]
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("cannot read \(path)\n".data(using: .utf8)!)
        exit(2)
    }
    let req = VNDetectFaceRectanglesRequest()
    try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    out[path] = (req.results ?? []).map { f in
        let b = f.boundingBox
        return [Double(b.origin.x), Double(1 - b.origin.y - b.height), Double(b.width), Double(b.height)]
    }
}
let data = try JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
