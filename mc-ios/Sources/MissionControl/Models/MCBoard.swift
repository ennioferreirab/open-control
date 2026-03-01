import Foundation

struct AgentMemoryModeEntry: Codable, Hashable, Sendable {
    let agentName: String
    let mode: AgentMemoryMode
}

struct MCBoard: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let name: String
    let displayName: String
    let description: String?
    let enabledAgents: [String]
    let agentMemoryModes: [AgentMemoryModeEntry]?
    let isDefault: Bool?
    let createdAt: String
    let updatedAt: String
    let deletedAt: String?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case name
        case displayName
        case description
        case enabledAgents
        case agentMemoryModes
        case isDefault
        case createdAt
        case updatedAt
        case deletedAt
    }
}
