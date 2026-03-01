import Foundation

struct TaskFile: Codable, Hashable, Sendable {
    let name: String
    let type: String
    let size: Int
    let subfolder: String
    let uploadedAt: String
}

struct MCTask: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let title: String
    let description: String?
    let status: TaskStatus
    let assignedAgent: String?
    let trustLevel: TrustLevel
    let reviewers: [String]?
    let tags: [String]?
    let taskTimeout: Int?
    let interAgentTimeout: Int?
    // executionPlan is `any` in schema — omitted pending AnyCodable support
    let supervisionMode: SupervisionMode?
    let stalledAt: String?
    let isManual: Bool?
    let isFavorite: Bool?
    let autoTitle: Bool?
    let awaitingKickoff: Bool?
    let deletedAt: String?
    let previousStatus: String?
    let boardId: String?
    let cronParentTaskId: String?
    let sourceAgent: String?
    let files: [TaskFile]?
    let createdAt: String
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case title
        case description
        case status
        case assignedAgent
        case trustLevel
        case reviewers
        case tags
        case taskTimeout
        case interAgentTimeout
        case supervisionMode
        case stalledAt
        case isManual
        case isFavorite
        case autoTitle
        case awaitingKickoff
        case deletedAt
        case previousStatus
        case boardId
        case cronParentTaskId
        case sourceAgent
        case files
        case createdAt
        case updatedAt
    }
}
