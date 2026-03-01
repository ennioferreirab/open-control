import Foundation

struct AgentVariable: Codable, Hashable, Sendable {
    let name: String
    let value: String
}

struct MCAgent: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let name: String
    let displayName: String
    let role: String
    let prompt: String?
    let soul: String?
    let skills: [String]
    let status: AgentStatus
    let enabled: Bool?
    let isSystem: Bool?
    let model: String?
    let reasoningLevel: String?
    let variables: [AgentVariable]?
    let lastActiveAt: String?
    let deletedAt: String?
    let memoryContent: String?
    let historyContent: String?
    let sessionData: String?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case name
        case displayName
        case role
        case prompt
        case soul
        case skills
        case status
        case enabled
        case isSystem
        case model
        case reasoningLevel
        case variables
        case lastActiveAt
        case deletedAt
        case memoryContent
        case historyContent
        case sessionData
    }
}
