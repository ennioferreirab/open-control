import Foundation
import SwiftUI

// MARK: - Task

enum TaskStatus: String, Codable, Hashable, Sendable, CaseIterable {
    case planning
    case ready
    case failed
    case inbox
    case assigned
    case inProgress = "in_progress"
    case review
    case done
    case retrying
    case crashed
    case deleted
}

enum TrustLevel: String, Codable, Hashable, Sendable, CaseIterable {
    case autonomous
    case agentReviewed = "agent_reviewed"
    case humanApproved = "human_approved"
}

enum SupervisionMode: String, Codable, Hashable, Sendable, CaseIterable {
    case autonomous
    case supervised
}

// MARK: - Step

enum StepStatus: String, Codable, Hashable, Sendable, CaseIterable {
    case planned
    case assigned
    case running
    case completed
    case crashed
    case blocked
    case waitingHuman = "waiting_human"
}

// MARK: - Agent

enum AgentStatus: String, Codable, Hashable, Sendable, CaseIterable {
    case active
    case idle
    case crashed
}

// MARK: - Message

enum AuthorType: String, Codable, Hashable, Sendable, CaseIterable {
    case agent
    case user
    case system
}

enum MessageType: String, Codable, Hashable, Sendable, CaseIterable {
    case work
    case reviewFeedback = "review_feedback"
    case approval
    case denial
    case systemEvent = "system_event"
    case userMessage = "user_message"
    case comment
}

enum MessageSubtype: String, Codable, Hashable, Sendable, CaseIterable {
    case stepCompletion = "step_completion"
    case userMessage = "user_message"
    case systemError = "system_error"
    case leadAgentPlan = "lead_agent_plan"
    case leadAgentChat = "lead_agent_chat"
    case comment
}

enum ArtifactAction: String, Codable, Hashable, Sendable, CaseIterable {
    case created
    case modified
    case deleted
}

// MARK: - Activity

enum ActivityEventType: String, Codable, Hashable, Sendable, CaseIterable {
    case taskCreated = "task_created"
    case taskPlanning = "task_planning"
    case taskFailed = "task_failed"
    case taskAssigned = "task_assigned"
    case taskStarted = "task_started"
    case taskCompleted = "task_completed"
    case taskCrashed = "task_crashed"
    case taskRetrying = "task_retrying"
    case taskReassigned = "task_reassigned"
    case reviewRequested = "review_requested"
    case reviewFeedback = "review_feedback"
    case reviewApproved = "review_approved"
    case hitlRequested = "hitl_requested"
    case hitlApproved = "hitl_approved"
    case hitlDenied = "hitl_denied"
    case agentConnected = "agent_connected"
    case agentDisconnected = "agent_disconnected"
    case agentCrashed = "agent_crashed"
    case systemError = "system_error"
    case taskDeleted = "task_deleted"
    case taskRestored = "task_restored"
    case agentConfigUpdated = "agent_config_updated"
    case agentActivated = "agent_activated"
    case agentDeactivated = "agent_deactivated"
    case agentDeleted = "agent_deleted"
    case agentRestored = "agent_restored"
    case bulkClearDone = "bulk_clear_done"
    case manualTaskStatusChanged = "manual_task_status_changed"
    case fileAttached = "file_attached"
    case agentOutput = "agent_output"
    case boardCreated = "board_created"
    case boardUpdated = "board_updated"
    case boardDeleted = "board_deleted"
    case threadMessageSent = "thread_message_sent"
    case taskDispatchStarted = "task_dispatch_started"
    case stepDispatched = "step_dispatched"
    case stepStarted = "step_started"
    case stepCompleted = "step_completed"
    case stepCreated = "step_created"
    case stepStatusChanged = "step_status_changed"
    case stepUnblocked = "step_unblocked"
}

// MARK: - Board

enum AgentMemoryMode: String, Codable, Hashable, Sendable, CaseIterable {
    case clean
    case withHistory = "with_history"
}

// MARK: - Tag

enum TagColor: String, Codable, Hashable, Sendable, CaseIterable {
    case blue
    case green
    case red
    case amber
    case violet
    case pink
    case orange
    case teal
}

// MARK: - Chat

// MARK: - TaskStatus Helpers

extension TaskStatus {
    var displayName: String {
        switch self {
        case .planning: return "Planning"
        case .ready: return "Ready"
        case .failed: return "Failed"
        case .inbox: return "Inbox"
        case .assigned: return "Assigned"
        case .inProgress: return "In Progress"
        case .review: return "Review"
        case .done: return "Done"
        case .retrying: return "Retrying"
        case .crashed: return "Crashed"
        case .deleted: return "Deleted"
        }
    }

    var color: Color {
        switch self {
        case .inbox: return .purple
        case .assigned: return .cyan
        case .inProgress: return .blue
        case .review: return .orange
        case .done: return .green
        case .crashed, .failed: return .red
        case .retrying: return .yellow
        case .planning, .ready: return .gray
        case .deleted: return .secondary
        }
    }
}

enum ChatAuthorType: String, Codable, Hashable, Sendable, CaseIterable {
    case user
    case agent
}

enum ChatStatus: String, Codable, Hashable, Sendable, CaseIterable {
    case pending
    case processing
    case done
}
