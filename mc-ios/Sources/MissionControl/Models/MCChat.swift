import Foundation

struct MCChat: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let agentName: String
    let authorName: String
    let authorType: ChatAuthorType
    let content: String
    let status: ChatStatus?
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case agentName
        case authorName
        case authorType
        case content
        case status
        case timestamp
    }
}
