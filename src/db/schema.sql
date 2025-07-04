-- Table to store the primary state for each ongoing conversation
CREATE TABLE Conversations (
    conversation_id UUID PRIMARY KEY,
    current_agent VARCHAR(255),
    context_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store tasks
CREATE TABLE tasks(
    task_id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES Conversations(conversation_id),
    goal VARCHAR(255),
    domain VARCHAR(255),
    task_status VARCHAR(50) CHECK (task_status IN ('pending', 'completed', 'canceled', 'deleted')),
    context TEXT,
    result TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store the history of each conversation
CREATE TABLE Messages (
    message_id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES Conversations(conversation_id),
    role VARCHAR(255),
    agent VARCHAR(255),
    content TEXT,
    task_id UUID REFERENCES tasks(task_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);