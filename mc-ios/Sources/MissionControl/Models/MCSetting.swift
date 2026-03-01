import Foundation

struct MCSetting: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let key: String
    let value: String

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case key
        case value
    }
}
