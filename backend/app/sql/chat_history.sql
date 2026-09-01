-- 对话历史表
CREATE TABLE IF NOT EXISTS chat_history
(
    id          BIGSERIAL PRIMARY KEY,
    message     TEXT NOT NULL,
    message_type VARCHAR(32),
    app_id       BIGSERIAL,
    user_id      BIGSERIAL,
    create_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_delete    SMALLINT DEFAULT 0 NOT NULL
);

-- 添加字段注释
COMMENT ON TABLE chat_history IS '对话历史';
COMMENT ON COLUMN chat_history.message IS '消息';
COMMENT ON COLUMN chat_history.message_type IS '消息类型：user/ai';
COMMENT ON COLUMN chat_history.app_id IS '应用id';
COMMENT ON COLUMN chat_history.user_id IS '创建用户id';
COMMENT ON COLUMN chat_history.create_time IS '创建时间';
COMMENT ON COLUMN chat_history.update_time IS '更新时间';
COMMENT ON COLUMN chat_history.is_delete IS '是否删除';
COMMENT ON COLUMN chat_history.id IS 'id';

-- 索引
CREATE INDEX idx_create_time ON chat_history (create_time);
CREATE INDEX idx_app_id_create_time ON chat_history (app_id, create_time);
CREATE INDEX idx_app_id ON chat_history (app_id);
