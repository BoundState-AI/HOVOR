// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "HovorKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "HovorKit", targets: ["HovorKit"])
    ],
    targets: [
        .target(name: "HovorKit"),
        .testTarget(name: "HovorKitTests", dependencies: ["HovorKit"]),
    ]
)
