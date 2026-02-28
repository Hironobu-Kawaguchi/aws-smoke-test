import { ChangeEvent, Fragment, useEffect, useRef, useState } from 'react'
import './App.css'

async function sha256Hex(message: string): Promise<string> {
  const data = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

interface Attachment {
  filename: string
  mimeType: string
  dataUrl: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  attachments?: Attachment[]
}

const SUPPORTED_FILE_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp']

function renderInline(text: string) {
  const chunks = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return chunks.map((chunk, i) => {
    if (chunk.startsWith('`') && chunk.endsWith('`')) {
      return <code key={i}>{chunk.slice(1, -1)}</code>
    }
    if (chunk.startsWith('**') && chunk.endsWith('**')) {
      return <strong key={i}>{chunk.slice(2, -2)}</strong>
    }
    return <Fragment key={i}>{chunk}</Fragment>
  })
}

function renderMarkdownLike(content: string) {
  const lines = content.split('\n')
  const blocks: JSX.Element[] = []
  let codeBuffer: string[] = []
  let inCodeBlock = false

  lines.forEach((line, index) => {
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        blocks.push(
          <pre key={`code-${index}`}>
            <code>{codeBuffer.join('\n')}</code>
          </pre>,
        )
        codeBuffer = []
      }
      inCodeBlock = !inCodeBlock
      return
    }

    if (inCodeBlock) {
      codeBuffer.push(line)
      return
    }

    if (line.startsWith('### ')) {
      blocks.push(<h3 key={`h3-${index}`}>{renderInline(line.slice(4))}</h3>)
      return
    }
    if (line.startsWith('## ')) {
      blocks.push(<h2 key={`h2-${index}`}>{renderInline(line.slice(3))}</h2>)
      return
    }
    if (line.startsWith('# ')) {
      blocks.push(<h1 key={`h1-${index}`}>{renderInline(line.slice(2))}</h1>)
      return
    }

    if (line.startsWith('- ')) {
      blocks.push(
        <li key={`li-${index}`}>
          {renderInline(line.slice(2))}
        </li>,
      )
      return
    }

    blocks.push(<p key={`p-${index}`}>{renderInline(line)}</p>)
  })

  if (codeBuffer.length > 0) {
    blocks.push(
      <pre key="code-last">
        <code>{codeBuffer.join('\n')}</code>
      </pre>,
    )
  }

  return blocks
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState('gpt-4o-mini')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [temperature, setTemperature] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [isComposing, setIsComposing] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files) return

    const newAttachments = await Promise.all(
      Array.from(files)
        .filter((file) => SUPPORTED_FILE_TYPES.includes(file.type))
        .map(
          (file) =>
            new Promise<Attachment>((resolve, reject) => {
              const reader = new FileReader()
              reader.onload = () => {
                const dataUrl = reader.result
                if (typeof dataUrl !== 'string') {
                  reject(new Error('ファイルの読み込みに失敗しました'))
                  return
                }
                resolve({ filename: file.name, mimeType: file.type, dataUrl })
              }
              reader.onerror = () => reject(new Error('ファイルの読み込みに失敗しました'))
              reader.readAsDataURL(file)
            }),
        ),
    )

    setAttachments((prev) => [...prev, ...newAttachments])
    event.target.value = ''
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  const sendMessage = async () => {
    const text = input.trim()
    if ((!text && attachments.length === 0) || loading) return

    const userMessage: Message = {
      role: 'user',
      content: text,
      attachments,
    }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setAttachments([])
    setLoading(true)

    try {
      const parsedTemperature = temperature.trim() === '' ? null : Number(temperature)
      const body = JSON.stringify({
        messages: updatedMessages,
        model: model.trim() || 'gpt-4o-mini',
        system_prompt: systemPrompt,
        temperature: Number.isFinite(parsedTemperature) ? parsedTemperature : null,
      })
      const bodyHash = await sha256Hex(body)
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-amz-content-sha256': bodyHash,
        },
        body,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setMessages([...updatedMessages, { role: 'assistant', content: data.message }])
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setMessages([
        ...updatedMessages,
        { role: 'assistant', content: `Error: ${errorMessage}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && !isComposing) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <h1>Chat</h1>
      </header>

      <section className="chat-settings">
        <label>
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label>
          Temperature
          <input
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            placeholder="例: 0.7"
          />
        </label>
        <label className="system-prompt">
          System Prompt
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={2}
            placeholder="システムプロンプトを入力"
          />
        </label>
      </section>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">{msg.role === 'user' ? 'You' : 'AI'}</div>
            <div className="chat-message-content markdown-body">{renderMarkdownLike(msg.content)}</div>
            {msg.attachments && msg.attachments.length > 0 && (
              <ul className="attachment-list">
                {msg.attachments.map((attachment, idx) => (
                  <li key={`${attachment.filename}-${idx}`}>{attachment.filename}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant">
            <div className="chat-message-role">AI</div>
            <div className="chat-message-content loading">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder="Type a message..."
          rows={2}
          disabled={loading}
        />
        <div className="chat-actions">
          <input
            type="file"
            multiple
            accept="application/pdf,image/png,image/jpeg,image/webp"
            onChange={handleFileChange}
            disabled={loading}
          />
          {attachments.length > 0 && (
            <ul className="attachment-list pending">
              {attachments.map((attachment, idx) => (
                <li key={`${attachment.filename}-${idx}`}>
                  {attachment.filename}
                  <button type="button" onClick={() => removeAttachment(idx)}>
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button onClick={sendMessage} disabled={loading || (!input.trim() && attachments.length === 0)}>
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
