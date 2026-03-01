import Foundation

struct MessageArtifact: Codable, Hashable, Sendable {
    let path: String
    let action: ArtifactAction
    let description: String?
    let diff: String?
}

struct MCMessage: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let taskId: String
    let stepId: String?
    let authorName: String
    let authorType: AuthorType
    let content: String
    let messageType: MessageType
    let type: MessageSubtype?
    let artifacts: [MessageArtifact]?
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case taskId
        case stepId
        case authorName
        case authorType
        case content
        case messageType
        case type
        case artifacts
        case timestamp
    }
}
