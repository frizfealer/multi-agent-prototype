-- Rename task table to tasks
ALTER TABLE task RENAME TO tasks;

-- Update the check constraint name for consistency
ALTER TABLE tasks RENAME CONSTRAINT task_status_check TO tasks_status_check;

-- Verify the rename
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE tablename IN ('conversations', 'messages', 'tasks')
ORDER BY tablename;

-- Check foreign key constraints that reference the renamed table
SELECT
    conname AS constraint_name,
    conrelid::regclass AS table_name,
    confrelid::regclass AS referenced_table
FROM pg_constraint
WHERE contype = 'f' 
AND (conrelid::regclass::text = 'messages' OR confrelid::regclass::text = 'tasks');