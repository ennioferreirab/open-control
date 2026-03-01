import Foundation

/// Represents a file document in Convex (standalone files collection).
/// Also used as a view model for task-embedded file attachments.
struct MCFile: Identifiable, Codable, Hashable, Sendable {
    let id: String
    let creationTime: Double
    let name: String
    let type: String
    let size: Int
    let subfolder: String
    let uploadedAt: String
    let taskId: String?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case creationTime = "_creationTime"
        case name
        case type
        case size
        case subfolder
        case uploadedAt
        case taskId
    }
}

extension MCFile {
    /// Create an MCFile from a TaskFile embedded in a task.
    init(from taskFile: TaskFile, taskId: String) {
        self.id = "\(taskId)-\(taskFile.name)"
        self.creationTime = 0
        self.name = taskFile.name
        self.type = taskFile.type
        self.size = taskFile.size
        self.subfolder = taskFile.subfolder
        self.uploadedAt = taskFile.uploadedAt
        self.taskId = taskId
    }
}
