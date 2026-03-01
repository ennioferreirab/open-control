import Foundation

struct MCActivity: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let taskId: String?
    let agentName: String?
    let eventType: ActivityEventType
    let description: String
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case taskId
        case agentName
        case eventType
        case description
        case timestamp
    }
}
