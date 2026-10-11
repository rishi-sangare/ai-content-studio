import Foundation
import Vision
import AppKit
// usage: ocr <image>...  → prints "<file>\t<text lines joined by ' | '>"
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("\(path)\t"); continue }
    let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    let lines = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    print("\((path as NSString).lastPathComponent)\t\(lines.joined(separator: " | "))")
}
