import {
  Fragment,
  useEffect,
  useMemo,
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function formatMegabytes(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

type ReasoningEffort = 'low' | 'medium' | 'high'

interface ModelMetadata {
  id: string
  supportsTemperature: boolean
  supportsReasoningEffort: boolean
  reasoningEffortOptions: ReasoningEffort[]
  defaultReasoningEffort: ReasoningEffort | null
  supportsWebSearch: boolean
  supportsPreviousResponse: boolean
}

const FALLBACK_MODELS: ModelMetadata[] = [
  {
    id: 'gpt-4.1',
    supportsTemperature: true,
    supportsReasoningEffort: false,
    reasoningEffortOptions: [],
    defaultReasoningEffort: null,
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-4.1-mini',
    supportsTemperature: true,
    supportsReasoningEffort: false,
    reasoningEffortOptions: [],
    defaultReasoningEffort: null,
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-5',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-5-mini',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-5-nano',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-5-chat-latest',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-5.2',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'gpt-5.2-pro',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'o4-mini',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'o3-deep-research',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'o4-mini-deep-research',
    supportsTemperature: false,
    supportsReasoningEffort: true,
    reasoningEffortOptions: ['low', 'medium', 'high'],
    defaultReasoningEffort: 'low',
    supportsWebSearch: true,
    supportsPreviousResponse: true,
  },
  {
    id: 'global.anthropic.claude-opus-4-6-v1',
    supportsTemperature: true,
    supportsReasoningEffort: false,
    reasoningEffortOptions: [],
    defaultReasoningEffort: null,
    supportsWebSearch: false,
    supportsPreviousResponse: false,
  },
  {
    id: 'global.anthropic.claude-sonnet-4-6',
    supportsTemperature: true,
    supportsReasoningEffort: false,
    reasoningEffortOptions: [],
    defaultReasoningEffort: null,
    supportsWebSearch: false,
    supportsPreviousResponse: false,
  },
  {
    id: 'global.anthropic.claude-haiku-4-5-20251001-v1:0',
    supportsTemperature: true,
    supportsReasoningEffort: false,
    reasoningEffortOptions: [],
    defaultReasoningEffort: null,
    supportsWebSearch: false,
    supportsPreviousResponse: false,
  },
]
const ALLOWED_ATTACHMENT_MIME_TYPES = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
])
const MAX_ATTACHMENTS = 4
const MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024
const MAX_TOTAL_ATTACHMENT_BYTES = 4 * 1024 * 1024
const MAX_OUTPUT_TOKENS = 4096
const MIN_OUTPUT_TOKENS = 1
const MIN_TEMPERATURE = 0
const MAX_TEMPERATURE = 2

type MessageRole = 'user' | 'assistant'

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
          <a
            key={`${match.index}-link`}
            href={linkMatch[2]}
            target="_blank"
            rel="noreferrer noopener"
          >
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

interface AttachmentMeta {
  name: string
  mimeType: string
}

interface RequestAttachment extends AttachmentMeta {
  dataUrl: string
}

interface Message {
  role: MessageRole
  content: string
  attachments?: AttachmentMeta[]
  metrics?: ResponseMetrics
}

interface ResponseMetrics {
  inputTokens?: number
  outputTokens?: number
  durationSeconds?: number
}

interface RequestMessage {
  role: MessageRole
  content: string
  attachments?: RequestAttachment[]
}

interface PendingAttachment extends RequestAttachment {
  sizeBytes: number
}

interface ChatSettings {
  model: string
  systemPrompt: string
  webSearchEnabled: boolean
  temperature: number
  reasoningEffort: ReasoningEffort
  maxOutputTokens: number
}

interface ChatApiResponse {
  message: string
  responseId?: string
  inputTokens?: number
  outputTokens?: number
  durationSeconds?: number
}

const DEFAULT_SETTINGS: ChatSettings = {
  model: FALLBACK_MODELS[1].id,
  systemPrompt: '',
  webSearchEnabled: true,
  temperature: 0.7,
  reasoningEffort: 'low',
  maxOutputTokens: 1000,
}

async function readFileAsAttachment(file: File): Promise<PendingAttachment> {
  return new Promise<PendingAttachment>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result !== 'string') {
        reject(new Error(`${file.name}: failed to load file`))
        return
      }

      resolve({
        name: file.name,
        mimeType: file.type,
        dataUrl: reader.result,
        sizeBytes: file.size,
      })
    }
    reader.onerror = () => reject(new Error(`${file.name}: failed to load file`))
    reader.readAsDataURL(file)
  })
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([])
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const [isLoadingAttachments, setIsLoadingAttachments] = useState(false)
  const [loading, setLoading] = useState(false)
  const [previousResponseId, setPreviousResponseId] = useState<string | null>(null)
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS)
  const [availableModels, setAvailableModels] = useState<ModelMetadata[]>(FALLBACK_MODELS)
  const [modelLoadError, setModelLoadError] = useState<string | null>(null)
  const loadingAttachmentsRef = useRef(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const activeModel = useMemo(
    () =>
      availableModels.find((model) => model.id === settings.model) ??
      availableModels[0] ??
      null,
    [availableModels, settings.model],
  )

  const totalPendingAttachmentBytes = useMemo(
    () =>
      pendingAttachments.reduce(
        (sum, attachment) => sum + attachment.sizeBytes,
        0,
      ),
    [pendingAttachments],
  )

  useEffect(() => {
    let cancelled = false

    const loadModels = async () => {
      try {
        const response = await fetch('/api/models')
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const data = (await response.json()) as ModelMetadata[]
        if (cancelled || data.length === 0) return

        setAvailableModels(data)
        setModelLoadError(null)
        setSettings((current) => {
          const nextModel = data.find((model) => model.id === current.model) ?? data[0]
          const nextReasoningEffort =
            nextModel.supportsReasoningEffort &&
            !nextModel.reasoningEffortOptions.includes(current.reasoningEffort)
              ? (nextModel.defaultReasoningEffort ??
                nextModel.reasoningEffortOptions[0] ??
                current.reasoningEffort)
              : current.reasoningEffort
          return {
            ...current,
            model: nextModel.id,
            reasoningEffort: nextReasoningEffort,
          }
        })
      } catch (error) {
        if (cancelled) return
        const message = error instanceof Error ? error.message : 'Unknown error'
        setModelLoadError(
          `Failed to load latest model list. Using fallback models. (${message})`,
        )
      }
    }

    void loadModels()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!activeModel || !activeModel.supportsReasoningEffort) return
    if (activeModel.reasoningEffortOptions.includes(settings.reasoningEffort)) return
    const fallbackReasoningEffort =
      activeModel.defaultReasoningEffort ??
      activeModel.reasoningEffortOptions[0] ??
      settings.reasoningEffort
    setSettings((current) => ({ ...current, reasoningEffort: fallbackReasoningEffort }))
  }, [activeModel, settings.reasoningEffort])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length === 0) return

    const errors: string[] = []
    const availableSlots = MAX_ATTACHMENTS - pendingAttachments.length
    if (availableSlots <= 0) {
      setAttachmentError(`You can attach up to ${MAX_ATTACHMENTS} files per message.`)
      return
    }

    const candidateFiles = files.slice(0, availableSlots)
    if (candidateFiles.length < files.length) {
      errors.push(`Only ${MAX_ATTACHMENTS} files can be attached per message.`)
    }

    let nextTotalBytes = totalPendingAttachmentBytes
    const acceptedFiles: File[] = []

    for (const file of candidateFiles) {
      if (!ALLOWED_ATTACHMENT_MIME_TYPES.has(file.type)) {
        errors.push(`${file.name}: unsupported file type.`)
        continue
      }

      if (file.size > MAX_ATTACHMENT_BYTES) {
        errors.push(
          `${file.name}: file exceeds ${formatMegabytes(MAX_ATTACHMENT_BYTES)} limit.`,
        )
        continue
      }

      if (nextTotalBytes + file.size > MAX_TOTAL_ATTACHMENT_BYTES) {
        errors.push(
          `Total attachment size exceeds ${formatMegabytes(MAX_TOTAL_ATTACHMENT_BYTES)}.`,
        )
        break
      }

      acceptedFiles.push(file)
      nextTotalBytes += file.size
    }

    if (acceptedFiles.length === 0) {
      setAttachmentError(errors.join(' ') || 'No files were added.')
      return
    }

    loadingAttachmentsRef.current = true
    setIsLoadingAttachments(true)

    try {
      const results = await Promise.allSettled(
        acceptedFiles.map((file) => readFileAsAttachment(file)),
      )
      const loadedAttachments: PendingAttachment[] = []
      let failedCount = 0

      for (const result of results) {
        if (result.status === 'fulfilled') {
          loadedAttachments.push(result.value)
        } else {
          failedCount += 1
        }
      }

      if (loadedAttachments.length > 0) {
        setPendingAttachments((current) => [...current, ...loadedAttachments])
      }

      if (failedCount > 0) {
        errors.push(`${failedCount} file(s) could not be loaded.`)
      }
      setAttachmentError(errors.length > 0 ? errors.join(' ') : null)
    } finally {
      loadingAttachmentsRef.current = false
      setIsLoadingAttachments(false)
    }
  }

  const removeAttachment = (index: number) => {
    setPendingAttachments((current) => current.filter((_, i) => i !== index))
    setAttachmentError(null)
  }

  const sendMessage = async () => {
    const text = input.trim()
    if (loadingAttachmentsRef.current) {
      setAttachmentError('Please wait until files finish loading.')
      return
    }
    if ((!text && pendingAttachments.length === 0) || loading) return

    const requestAttachments: RequestAttachment[] = pendingAttachments.map(
      ({ name, mimeType, dataUrl }) => ({ name, mimeType, dataUrl }),
    )
    const messageAttachments: AttachmentMeta[] = pendingAttachments.map(
      ({ name, mimeType }) => ({ name, mimeType }),
    )

    const userMessage: Message = {
      role: 'user',
      content: text,
      attachments: messageAttachments.length > 0 ? messageAttachments : undefined,
    }
    const updatedMessages = [...messages, userMessage]
    const requestMessage: RequestMessage = {
      role: 'user',
      content: text,
      attachments: requestAttachments.length > 0 ? requestAttachments : undefined,
    }

    setMessages(updatedMessages)
    setInput('')
    setPendingAttachments([])
    setAttachmentError(null)
    setLoading(true)

    try {
      const body = JSON.stringify({
        messages: [requestMessage],
        model: settings.model,
        systemPrompt: settings.systemPrompt,
        webSearchEnabled: settings.webSearchEnabled,
        temperature: activeModel?.supportsTemperature ? settings.temperature : undefined,
        reasoningEffort: activeModel?.supportsReasoningEffort
          ? settings.reasoningEffort
          : undefined,
        maxOutputTokens: settings.maxOutputTokens,
        previousResponseId:
          activeModel?.supportsPreviousResponse !== false
            ? (previousResponseId ?? undefined)
            : undefined,
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

      const data = (await response.json()) as ChatApiResponse
      setPreviousResponseId(typeof data.responseId === 'string' ? data.responseId : null)
      setMessages([
        ...updatedMessages,
        {
          role: 'assistant',
          content: data.message,
          metrics: {
            inputTokens: data.inputTokens,
            outputTokens: data.outputTokens,
            durationSeconds: data.durationSeconds,
          },
        },
      ])
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
    if (e.nativeEvent.isComposing || e.key === 'Process') return
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
          <select
            value={settings.model}
            onChange={(e) =>
              setSettings((current) => ({ ...current, model: e.target.value }))
            }
            disabled={loading}
          >
            {availableModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          System Prompt
          <input
            value={settings.systemPrompt}
            onChange={(e) =>
              setSettings((current) => ({
                ...current,
                systemPrompt: e.target.value,
              }))
            }
            disabled={loading}
          />
        </label>
        {activeModel?.supportsWebSearch !== false && (
          <label className="chat-toggle">
            Web Search
            <input
              type="checkbox"
              checked={settings.webSearchEnabled}
              onChange={(e) =>
                setSettings((current) => ({
                  ...current,
                  webSearchEnabled: e.target.checked,
                }))
              }
              disabled={loading}
            />
          </label>
        )}
        {activeModel?.supportsTemperature && (
          <label>
            Temperature
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={settings.temperature}
              onChange={(e) => {
                if (e.target.value.trim() === '') return
                const parsed = Number.parseFloat(e.target.value)
                if (!Number.isFinite(parsed)) return
                setSettings((current) => ({
                  ...current,
                  temperature: clamp(parsed, MIN_TEMPERATURE, MAX_TEMPERATURE),
                }))
              }}
              disabled={loading}
            />
          </label>
        )}
        {activeModel?.supportsReasoningEffort && (
          <label>
            Reasoning Effort
            <select
              value={settings.reasoningEffort}
              onChange={(e) =>
                setSettings((current) => ({
                  ...current,
                  reasoningEffort: e.target.value as ReasoningEffort,
                }))
              }
              disabled={loading}
            >
              {activeModel.reasoningEffortOptions.map((effort) => (
                <option key={effort} value={effort}>
                  {effort}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Max Tokens
          <input
            type="number"
            min={1}
            max={4096}
            value={settings.maxOutputTokens}
            onChange={(e) => {
              if (e.target.value.trim() === '') return
              const parsed = Number.parseInt(e.target.value, 10)
              if (!Number.isFinite(parsed)) return
              setSettings((current) => ({
                ...current,
                maxOutputTokens: clamp(parsed, MIN_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS),
              }))
            }}
            disabled={loading}
          />
        </label>
      </section>
      {modelLoadError && (
        <p className="settings-error" role="status">
          {modelLoadError}
        </p>
      )}

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">{msg.role === 'user' ? 'You' : 'AI'}</div>
            <div className="chat-message-content markdown">{renderMarkdown(msg.content)}</div>
            {msg.role === 'assistant' && msg.metrics && (
              <div className="chat-message-metrics">
                <span>入力: {msg.metrics.inputTokens?.toLocaleString() ?? '-'} tokens</span>
                <span>出力: {msg.metrics.outputTokens?.toLocaleString() ?? '-'} tokens</span>
                <span>応答時間: {msg.metrics.durationSeconds?.toFixed(2) ?? '-'}秒</span>
              </div>
            )}
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
            <span>Attach</span>
            <input
              className="file-picker-input"
              type="file"
              accept="application/pdf,image/*"
              multiple
              onChange={handleFileChange}
              disabled={loading || isLoadingAttachments}
            />
          </label>
          <button
            onClick={sendMessage}
            disabled={
              loading ||
              isLoadingAttachments ||
              (!input.trim() && pendingAttachments.length === 0)
            }
          >
            {isLoadingAttachments ? 'Loading files...' : 'Send'}
          </button>
        </div>
      </div>
      {pendingAttachments.length > 0 && (
        <div className="pending-attachments">
          {pendingAttachments.map((attachment, index) => (
            <button
              key={`${attachment.name}-${index}`}
              onClick={() => removeAttachment(index)}
              disabled={loading || isLoadingAttachments}
            >
              {attachment.name} ×
            </button>
          ))}
        </div>
      )}
      {attachmentError && (
        <p className="attachment-error" role="alert">
          {attachmentError}
        </p>
      )}
    </div>
  )
}

export default App
