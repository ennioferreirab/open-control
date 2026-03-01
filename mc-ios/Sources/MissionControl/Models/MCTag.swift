import Foundation

struct MCTag: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let name: String
    let color: TagColor
    let attributeIds: [String]?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case name
        case color
        case attributeIds
    }
}
