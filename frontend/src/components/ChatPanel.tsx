import { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, Upload, Spin, message as antMsg } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, FileExcelOutlined, LoadingOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd';
import { uploadFile } from '../api/client';
import './ChatPanel.css';

const { TextArea } = Input;

// ============================================================
// Types
// ============================================================

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: Array<{ tool: string; args: Record<string, unknown>; result?: string }>;
  fileId?: string;
  filename?: string;
  reportUrl?: string;
}

interface SSEEvent {
  type: 'text' | 'tool_call' | 'tool_result' | 'error' | 'done';
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  success?: boolean;
  summary?: string;
  message?: string;
}

// ============================================================
// Component
// ============================================================

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: '你好！我是建筑能耗分析助手 🤖\n\n上传 Excel/CSV 能耗数据文件，我会自动分析并生成报告。\n\n你也可以直接粘贴表格数据，或者跟我说你想分析什么。',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState<string>(() => 's' + Date.now().toString(36));
  const [uploadedFile, setUploadedFile] = useState<{ id: string; name: string } | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  // ---- File Upload ----
  const handleFileUpload = useCallback(async (file: File) => {
    try {
      const res = await uploadFile(file);
      setUploadedFile({ id: res.file_id, name: res.filename });
      antMsg.success(`文件 "${res.filename}" 已就绪`);
    } catch {
      antMsg.error('文件上传失败');
    }
    return false;
  }, []);

  // ---- Send Message ----
  const handleSend = useCallback(async () => {
    const msgText = input.trim();
    if (!msgText && !uploadedFile) return;

    // Add user message
    const userMsg: ChatMessage = {
      role: 'user',
      content: msgText || '请分析这个文件',
      fileId: uploadedFile?.id,
      filename: uploadedFile?.name,
    };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    // Add placeholder for assistant response
    const assistantIdx = newMessages.length;
    setMessages([...newMessages, { role: 'assistant', content: '', toolCalls: [] }]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msgText || '请分析这个文件',
          file_id: uploadedFile?.id || undefined,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response stream');

      const decoder = new TextDecoder();
      let buffer = '';
      let currentContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event: SSEEvent = JSON.parse(line.slice(6));

            setMessages(prev => {
              const updated = [...prev];
              const last = updated[assistantIdx] || { role: 'assistant', content: '', toolCalls: [] };

              if (event.type === 'text' && event.text) {
                currentContent += event.text;
                updated[assistantIdx] = { ...last, content: currentContent, toolCalls: last.toolCalls };
              } else if (event.type === 'tool_call') {
                const tc = [...(last.toolCalls || []), { tool: event.tool || '', args: event.args || {} }];
                updated[assistantIdx] = { ...last, content: currentContent, toolCalls: tc };
              } else if (event.type === 'tool_result') {
                const tc = [...(last.toolCalls || [])];
                if (tc.length > 0) {
                  tc[tc.length - 1] = { ...tc[tc.length - 1], result: event.summary };
                }
                updated[assistantIdx] = { ...last, content: currentContent, toolCalls: tc };
              } else if (event.type === 'error') {
                updated[assistantIdx] = { ...last, content: `❌ 错误: ${event.message}`, toolCalls: last.toolCalls };
              }

              return updated;
            });
          } catch { /* skip malformed events */ }
        }
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : '未知错误';
      setMessages(prev => {
        const updated = [...prev];
        updated[assistantIdx] = { role: 'assistant', content: `❌ 请求失败: ${errMsg}` };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  }, [input, messages, sessionId, uploadedFile]);

  // ---- Render helper ----
  const renderContent = (msg: ChatMessage) => {
    const text = msg.content;
    if (!text && (!msg.toolCalls || msg.toolCalls.length === 0)) {
      return <Spin indicator={<LoadingOutlined />} />;
    }

    return (
      <div>
        {text ? (
          <div className="chat-markdown" dangerouslySetInnerHTML={{
            __html: text
              .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
              .replace(/\*(.*?)\*/g, '<em>$1</em>')
              .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
              .replace(/`([^`]+)`/g, '<code>$1</code>')
              .replace(/^- (.*)/gm, '• $1')
              .replace(/\n\n/g, '</p><p>')
              .replace(/\n/g, '<br/>')
              .replace(/^/, '<p>')
              .replace(/$/, '</p>'),
          }} />
        ) : null}

        {/* Tool call indicators */}
        {msg.toolCalls && msg.toolCalls.length > 0 ? (
          <div className="tool-calls">
            {msg.toolCalls.map((tc, i) => (
              <div key={i} className={`tool-call ${tc.result ? 'done' : 'running'}`}>
                <span className="tool-icon">{tc.result ? '✅' : '🔄'}</span>
                <span className="tool-name">{_toolLabel(tc.tool)}</span>
                {tc.result ? <span className="tool-result">{tc.result}</span> : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-avatar">
              {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
            </div>
            <div className="chat-bubble">
              {/* File attachment indicator */}
              {msg.fileId ? (
                <div className="file-attachment">
                  <FileExcelOutlined /> {msg.filename || msg.fileId}
                </div>
              ) : null}
              {renderContent(msg)}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-row">
          <Upload
            accept=".xlsx,.xls,.csv"
            maxCount={1}
            fileList={fileList}
            onChange={({ fileList: fl }) => setFileList(fl)}
            beforeUpload={handleFileUpload}
            showUploadList={false}
          >
            <Button icon={<FileExcelOutlined />} size="large" disabled={loading}>
              {uploadedFile ? uploadedFile.name : '上传文件'}
            </Button>
          </Upload>

          <TextArea
            value={input}
            onChange={e => setInput(e.target.value)}
            onPressEnter={e => {
              if (!e.shiftKey) { e.preventDefault(); handleSend(); }
            }}
            placeholder={uploadedFile ? '输入消息，或直接按回车开始分析...' : '上传文件或粘贴数据后发送...'}
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            className="chat-input"
          />

          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            size="large"
            disabled={!uploadedFile && !input.trim()}
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---- Helpers ----

function _toolLabel(tool: string): string {
  const labels: Record<string, string> = {
    'preview_excel_file': '📋 查看文件结构',
    'parse_excel_auto': '🔍 自动解析数据',
    'parse_transposed_sum': '🏢 按建筑汇总解析',
    'run_full_analysis': '📊 运行能耗分析',
    'generate_word_report': '📄 生成 Word 报告',
  };
  return labels[tool] || tool;
}
