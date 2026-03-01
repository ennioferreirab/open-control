import Foundation

struct MCStep: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let taskId: String
    let title: String
    let description: String
    let assignedAgent: String
    let status: StepStatus
    let blockedBy: [String]?
    let parallelGroup: Int
    let order: Int
    let createdAt: String
    let startedAt: String?
    let completedAt: String?
    let errorMessage: String?
    let attachedFiles: [String]?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case taskId
        case title
        case description
        case assignedAgent
        case status
        case blockedBy
        case parallelGroup
        case order
        case createdAt
        case startedAt
        case completedAt
        case errorMessage
        case attachedFiles
    }
}
