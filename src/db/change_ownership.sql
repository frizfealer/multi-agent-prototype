-- Change ownership of conversations and messages tables to test_user
ALTER TABLE conversations OWNER TO test_user;
ALTER TABLE messages OWNER TO test_user;
ALTER TABLE task OWNER TO test_user;
-- Verify the ownership change
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE tablename IN ('conversations', 'messages', 'task')
ORDER BY tablename;