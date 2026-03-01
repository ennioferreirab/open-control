// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "MissionControl",
    platforms: [
        .iOS(.v26),
        .macOS(.v26)
    ],
    products: [
        .library(
            name: "MissionControl",
            targets: ["MissionControl"]
        )
    ],
    dependencies: [
        .package(
            url: "https://github.com/get-convex/convex-swift",
            .upToNextMajor(from: "0.8.1")
        )
    ],
    targets: [
        .target(
            name: "MissionControl",
            dependencies: [
                .product(name: "ConvexMobile", package: "convex-swift")
            ]
        )
    ]
)
