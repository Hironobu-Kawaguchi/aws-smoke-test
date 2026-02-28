import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import './App.css'

async function sha256Hex(message: string): Promise<string> {
  const data = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^\s)]+)\))/g
  let lastIndex = 0
  let match = tokenRegex.exec(text)

  while (match !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index))
    }

    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(<strong key={`${match.index}-bold`}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('*') && token.endsWith('*')) {
      nodes.push(<em key={`${match.index}-italic`}>{token.slice(1, -1)}</em>)
    } else if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(<code key={`${match.index}-code`}>{token.slice(1, -1)}</code>)
    } else {
      const linkMatch = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/)
      if (linkMatch) {
        nodes.push(
          <a key={`${match.index}-link`} href={linkMatch[2]} target="_blank" rel="noreferrer">
            {linkMatch[1]}
          </a>,
        )
      } else {
        nodes.push(token)
      }
    }

    lastIndex = tokenRegex.lastIndex
    match = tokenRegex.exec(text)
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }

  return nodes
}

function renderMarkdown(message: string): ReactNode[] {
  const lines = message.split('\n')
  const nodes: ReactNode[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]

    if (line.startsWith('```')) {
      const codeLines: string[] = []
      index += 1
      while (index < lines.length && !lines[index].startsWith('```')) {
        codeLines.push(lines[index])
        index += 1
      }
      nodes.push(
        <pre key={`pre-${index}`}>
          <code>{codeLines.join('\n')}</code>
        </pre>,
      )
      index += 1
      continue
    }

    if (line.startsWith('### ')) {
      nodes.push(<h3 key={`h3-${index}`}>{renderInlineMarkdown(line.slice(4))}</h3>)
      index += 1
      continue
    }

    if (line.startsWith('## ')) {
      nodes.push(<h2 key={`h2-${index}`}>{renderInlineMarkdown(line.slice(3))}</h2>)
      index += 1
      continue
    }

    if (line.startsWith('# ')) {
      nodes.push(<h1 key={`h1-${index}`}>{renderInlineMarkdown(line.slice(2))}</h1>)
      index += 1
      continue
    }

    if (line.startsWith('- ')) {
      const items: string[] = []
      while (index < lines.length && lines[index].startsWith('- ')) {
        items.push(lines[index].slice(2))
        index += 1
      }
      nodes.push(
        <ul key={`ul-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`li-${index}-${itemIndex}`}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>,
      )
      continue
    }

    if (line.trim() === '') {
      index += 1
      continue
    }

    const paragraph: string[] = [line]
    index += 1
    while (
      index < lines.length &&
      lines[index].trim() !== '' &&
      !lines[index].startsWith('#') &&
      !lines[index].startsWith('- ') &&
      !lines[index].startsWith('```')
    ) {
      paragraph.push(lines[index])
      index += 1
    }

    nodes.push(
      <p key={`p-${index}`}>
        {paragraph.map((text, lineIndex) => (
          <Fragment key={`p-${index}-${lineIndex}`}>
            {lineIndex > 0 && <br />}
            {renderInlineMarkdown(text)}
          </Fragment>
        ))}
      </p>,
    )
  }

  return nodes
}

interface Attachment {
  name: string
  mimeType: string
  dataUrl: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  attachments?: Attachment[]
}

interface ChatSettings {
  model: string
  systemPrompt: string
  temperature: number
  maxOutputTokens: number
}

const DEFAULT_SETTINGS: ChatSettings = {
  model: 'gpt-4o-mini',
  systemPrompt: '',
  temperature: 0.7,
  maxOutputTokens: 1000,
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [loading, setLoading] = useState(false)
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    if (files.length === 0) return

    const nextAttachments = await Promise.all(
      files.map(
        (file) =>
          new Promise<Attachment>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => {
              if (typeof reader.result !== 'string') {
                reject(new Error('Failed to load file'))
                return
              }
              resolve({
                name: file.name,
                mimeType: file.type || 'application/octet-stream',
                dataUrl: reader.result,
              })
            }
            reader.onerror = () => reject(new Error('Failed to load file'))
            reader.readAsDataURL(file)
          }),
      ),
    )

    setAttachments((current) => [...current, ...nextAttachments])
    event.target.value = ''
  }

  const removeAttachment = (index: number) => {
    setAttachments((current) => current.filter((_, i) => i !== index))
  }

  const sendMessage = async () => {
    const text = input.trim()
    if ((!text && attachments.length === 0) || loading) return

    const userMessage: Message = {
      role: 'user',
      content: text,
      attachments: attachments.length > 0 ? attachments : undefined,
    }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setAttachments([])
    setLoading(true)

    try {
      const body = JSON.stringify({
        messages: updatedMessages,
        model: settings.model,
        systemPrompt: settings.systemPrompt,
        temperature: settings.temperature,
        maxOutputTokens: settings.maxOutputTokens,
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

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    if (e.key === 'Enter' && !e.shiftKey) {
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
          <input
            value={settings.model}
            onChange={(e) => setSettings({ ...settings, model: e.target.value })}
            disabled={loading}
          />
        </label>
        <label>
          System Prompt
          <input
            value={settings.systemPrompt}
            onChange={(e) =>
              setSettings({ ...settings, systemPrompt: e.target.value })
            }
            disabled={loading}
          />
        </label>
        <label>
          Temperature
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={settings.temperature}
            onChange={(e) =>
              setSettings({ ...settings, temperature: Number(e.target.value) })
            }
            disabled={loading}
          />
        </label>
        <label>
          Max Tokens
          <input
            type="number"
            min={1}
            max={4096}
            value={settings.maxOutputTokens}
            onChange={(e) =>
              setSettings({ ...settings, maxOutputTokens: Number(e.target.value) })
            }
            disabled={loading}
          />
        </label>
      </section>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">{msg.role === 'user' ? 'You' : 'AI'}</div>
            <div className="chat-message-content markdown">{renderMarkdown(msg.content)}</div>
            {msg.attachments && msg.attachments.length > 0 && (
              <ul className="attachment-list">
                {msg.attachments.map((attachment, index) => (
                  <li key={`${attachment.name}-${index}`}>{attachment.name}</li>
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
          placeholder="Type a message..."
          rows={2}
          disabled={loading}
        />
        <div className="chat-input-actions">
          <label className="file-picker">
            Attach
            <input
              type="file"
              accept="application/pdf,image/*"
              multiple
              onChange={handleFileChange}
              disabled={loading}
            />
          </label>
          <button
            onClick={sendMessage}
            disabled={loading || (!input.trim() && attachments.length === 0)}
          >
            Send
          </button>
        </div>
      </div>
      {attachments.length > 0 && (
        <div className="pending-attachments">
          {attachments.map((attachment, index) => (
            <button
              key={`${attachment.name}-${index}`}
              onClick={() => removeAttachment(index)}
              disabled={loading}
            >
              {attachment.name} ×
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
