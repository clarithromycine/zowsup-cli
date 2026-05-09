import React, { useEffect, useState, useCallback } from 'react'
import {
  Tabs,
  Card,
  Button,
  Input,
  Select,
  Upload,
  Table,
  Tag,
  Image,
  Tooltip,
  Popconfirm,
  Modal,
  Form,
  Typography,
  Space,
  message,
  Empty,
  Spin,
  Row,
  Col,
  Badge,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  UploadOutlined,
  RobotOutlined,
  FileTextOutlined,
  PictureOutlined,
  ThunderboltOutlined,
  SendOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { useTranslation } from 'react-i18next'
import apiClient from '../api/client'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

// ---- Types ---------------------------------------------------------------

interface Material {
  id: number
  name: string
  type: 'image' | 'text' | 'document' | 'video' | 'audio'
  content: string | null
  file_path: string | null
  mime_type: string | null
  tags: string[]
  ai_prompt: string | null
  created_at: string
}

interface MessageTemplate {
  id: number
  name: string
  type: 'text' | 'image' | 'document' | 'location' | 'buttons' | 'list'
  content_json: Record<string, unknown>
  description: string | null
  tags: string[]
  created_at: string
}

// ---- API helpers ---------------------------------------------------------

async function fetchMaterials(type?: string): Promise<Material[]> {
  const params = type ? { type } : {}
  const { data } = await apiClient.get('/materials/', { params })
  return data.materials
}

async function deleteMaterial(id: number): Promise<void> {
  await apiClient.delete(`/materials/${id}`)
}

async function uploadMaterial(file: File, name: string): Promise<Material> {
  const form = new FormData()
  form.append('file', file)
  form.append('name', name)
  const { data } = await apiClient.post('/materials/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

async function generateImage(prompt: string, name: string): Promise<{ generated: boolean; content?: string; error?: string }> {
  const { data } = await apiClient.post('/materials/generate', { prompt, name, tags: ['ai-generated'] })
  return data
}

async function fetchTemplates(): Promise<MessageTemplate[]> {
  const { data } = await apiClient.get('/materials/templates')
  return data.templates
}

async function createTemplate(payload: Partial<MessageTemplate>): Promise<MessageTemplate> {
  const { data } = await apiClient.post('/materials/templates', payload)
  return data
}

async function deleteTemplate(id: number): Promise<void> {
  await apiClient.delete(`/materials/templates/${id}`)
}

// ---- Material type badge -----------------------------------------------

const TYPE_COLORS: Record<string, string> = {
  image: 'blue',
  text: 'green',
  document: 'orange',
  video: 'purple',
  audio: 'cyan',
}

// ---- Sub-pages -----------------------------------------------------------

/** Tab 1: Material list */
const MaterialList: React.FC = () => {
  const { t } = useTranslation()
  const [materials, setMaterials] = useState<Material[]>([])
  const [loading, setLoading] = useState(false)
  const [typeFilter, setTypeFilter] = useState<string | undefined>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setMaterials(await fetchMaterials(typeFilter))
    } catch {
      message.error(t('materials.loadError'))
    } finally {
      setLoading(false)
    }
  }, [typeFilter, t])

  useEffect(() => { load() }, [load])

  async function handleDelete(id: number) {
    try {
      await deleteMaterial(id)
      message.success(t('materials.deleted'))
      load()
    } catch {
      message.error(t('materials.deleteFailed'))
    }
  }

  const columns = [
    {
      title: t('materials.name'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string, row: Material) => (
        <Space>
          {row.type === 'image' && row.content && (
            <Image src={row.content} width={40} height={40} style={{ objectFit: 'cover', borderRadius: 4 }} />
          )}
          <Text>{name}</Text>
        </Space>
      ),
    },
    {
      title: t('materials.type'),
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => <Tag color={TYPE_COLORS[type] ?? 'default'}>{type}</Tag>,
    },
    {
      title: t('materials.tags'),
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => tags.map((t) => <Tag key={t}>{t}</Tag>),
    },
    {
      title: t('materials.aiPrompt'),
      dataIndex: 'ai_prompt',
      key: 'ai_prompt',
      render: (p: string | null) =>
        p ? <Tooltip title={p}><Tag icon={<RobotOutlined />} color="gold">AI</Tag></Tooltip> : null,
    },
    {
      title: t('common.time'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (ts: string) => new Date(ts).toLocaleString('zh-CN'),
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_: unknown, row: Material) => (
        <Popconfirm
          title={t('materials.confirmDelete')}
          onConfirm={() => handleDelete(row.id)}
          okText={t('common.confirm')}
          cancelText={t('common.cancel')}
        >
          <Button danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <Card
      title={<><PictureOutlined style={{ marginRight: 8 }} />{t('materials.library')}</>}
      extra={
        <Space>
          <Select
            allowClear
            placeholder={t('materials.filterType')}
            style={{ width: 140 }}
            onChange={setTypeFilter}
            options={[
              { label: t('materials.typeImage'), value: 'image' },
              { label: t('materials.typeText'), value: 'text' },
              { label: t('materials.typeDocument'), value: 'document' },
              { label: t('materials.typeVideo'), value: 'video' },
              { label: t('materials.typeAudio'), value: 'audio' },
            ]}
          />
          <Button icon={<UploadOutlined />} onClick={() => document.getElementById('mat-upload-btn')?.click()}>
            {t('materials.upload')}
          </Button>
          {/* Hidden upload — triggered by button above */}
          <Upload
            id="mat-upload-btn"
            showUploadList={false}
            customRequest={async ({ file, onSuccess, onError }) => {
              try {
                const f = file as File
                await uploadMaterial(f, f.name)
                message.success(t('materials.uploaded'))
                load()
                onSuccess?.({})
              } catch {
                message.error(t('materials.uploadFailed'))
                onError?.(new Error('upload failed'))
              }
            }}
          >
            <span style={{ display: 'none' }} />
          </Upload>
        </Space>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={materials}
        columns={columns}
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: <Empty description={t('materials.empty')} /> }}
      />
    </Card>
  )
}

/** Tab 2: AI image generation */
const AIGenerate: React.FC = () => {
  const { t } = useTranslation()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ url?: string; error?: string } | null>(null)

  async function handleGenerate(values: { prompt: string; name?: string }) {
    setLoading(true)
    setResult(null)
    try {
      const res = await generateImage(values.prompt, values.name || t('materials.aiDefaultName'))
      if (res.generated && res.content) {
        setResult({ url: res.content })
        message.success(t('materials.aiGenerated'))
      } else {
        setResult({ error: res.error })
        message.warning(res.error || t('materials.aiNotConfigured'))
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setResult({ error: msg })
      message.error(t('materials.aiGenFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card title={<><RobotOutlined style={{ marginRight: 8 }} />{t('materials.aiGenerate')}</>}>
      <Row gutter={24}>
        <Col xs={24} md={12}>
          <Form form={form} onFinish={handleGenerate} layout="vertical">
            <Form.Item
              name="prompt"
              label={t('materials.aiPromptLabel')}
              rules={[{ required: true, message: t('materials.aiPromptRequired') }]}
            >
              <TextArea
                rows={5}
                placeholder={t('materials.aiPromptPlaceholder')}
                maxLength={1000}
                showCount
              />
            </Form.Item>
            <Form.Item name="name" label={t('materials.nameLabel')}>
              <Input placeholder={t('materials.aiDefaultName')} maxLength={100} />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<ThunderboltOutlined />}
                block
              >
                {t('materials.generateBtn')}
              </Button>
            </Form.Item>
          </Form>
          <div style={{ background: '#f9f9f9', padding: 12, borderRadius: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('materials.aiConfigHint')}
            </Text>
            <br />
            <Text code style={{ fontSize: 11 }}>IMAGE_GEN_API_KEY / OPENAI_API_KEY</Text>
          </div>
        </Col>

        <Col xs={24} md={12} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          {loading && <Spin tip={t('materials.aiGenerating')} size="large" />}
          {!loading && result?.url && (
            <Image
              src={result.url}
              style={{ maxWidth: '100%', borderRadius: 8 }}
              fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            />
          )}
          {!loading && result?.error && (
            <div style={{ padding: 20, textAlign: 'center' }}>
              <Text type="danger">{result.error}</Text>
            </div>
          )}
          {!loading && !result && (
            <Empty description={t('materials.aiPromptHint')} />
          )}
        </Col>
      </Row>
    </Card>
  )
}

/** Tab 3: WhatsApp message templates */
const MessageTemplates: React.FC = () => {
  const { t } = useTranslation()
  const [templates, setTemplates] = useState<MessageTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setTemplates(await fetchTemplates())
    } catch {
      message.error(t('materials.loadError'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { load() }, [load])

  async function handleCreate(values: { name: string; type: string; description?: string; content: string }) {
    try {
      let parsed: Record<string, unknown>
      try {
        parsed = JSON.parse(values.content)
      } catch {
        message.error(t('materials.invalidJson'))
        return
      }
      await createTemplate({
        name: values.name,
        type: values.type as MessageTemplate['type'],
        content_json: parsed,
        description: values.description,
      })
      message.success(t('materials.templateCreated'))
      setShowModal(false)
      form.resetFields()
      load()
    } catch {
      message.error(t('materials.templateCreateFailed'))
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteTemplate(id)
      message.success(t('materials.templateDeleted'))
      load()
    } catch {
      message.error(t('materials.deleteFailed'))
    }
  }

  // Starter templates for each type
  const STARTER_CONTENT: Record<string, string> = {
    text: JSON.stringify({ text: 'Hello, how can I help you?' }, null, 2),
    image: JSON.stringify({ image_url: 'https://...', caption: 'Caption text' }, null, 2),
    document: JSON.stringify({ url: 'https://...', filename: 'document.pdf', caption: 'Document' }, null, 2),
    location: JSON.stringify({ latitude: 0, longitude: 0, name: 'Location name', address: 'Address' }, null, 2),
    buttons: JSON.stringify({
      body: 'Choose an option:',
      buttons: [{ id: '1', title: 'Option A' }, { id: '2', title: 'Option B' }],
    }, null, 2),
    list: JSON.stringify({
      body: 'Select from list:',
      button: 'View options',
      sections: [{ title: 'Section 1', rows: [{ id: '1', title: 'Item 1' }] }],
    }, null, 2),
  }

  const columns = [
    { title: t('materials.name'), dataIndex: 'name', key: 'name' },
    {
      title: t('materials.type'),
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => <Tag color="geekblue">{type}</Tag>,
    },
    { title: t('materials.description'), dataIndex: 'description', key: 'description' },
    {
      title: t('materials.tags'),
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => tags.map((tg) => <Tag key={tg}>{tg}</Tag>),
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_: unknown, row: MessageTemplate) => (
        <Popconfirm
          title={t('materials.confirmDelete')}
          onConfirm={() => handleDelete(row.id)}
          okText={t('common.confirm')}
          cancelText={t('common.cancel')}
        >
          <Button danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <>
      <Card
        title={<><SendOutlined style={{ marginRight: 8 }} />{t('materials.templates')}</>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
            {t('materials.addTemplate')}
          </Button>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={templates}
          columns={columns}
          pagination={{ pageSize: 20 }}
          expandable={{
            expandedRowRender: (row) => (
              <pre style={{ background: '#f6f6f6', padding: 12, borderRadius: 6, fontSize: 12 }}>
                {JSON.stringify(row.content_json, null, 2)}
              </pre>
            ),
          }}
          locale={{ emptyText: <Empty description={t('materials.noTemplates')} /> }}
        />
      </Card>

      <Modal
        title={t('materials.addTemplate')}
        open={showModal}
        onCancel={() => { setShowModal(false); form.resetFields() }}
        onOk={() => form.submit()}
        width={640}
        okText={t('common.save')}
        cancelText={t('common.cancel')}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label={t('materials.templateName')} rules={[{ required: true }]}>
            <Input placeholder={t('materials.templateNamePlaceholder')} maxLength={80} />
          </Form.Item>
          <Form.Item name="type" label={t('materials.type')} rules={[{ required: true }]} initialValue="text">
            <Select
              options={['text', 'image', 'document', 'location', 'buttons', 'list'].map((v) => ({ label: v, value: v }))}
              onChange={(v) => {
                form.setFieldValue('content', STARTER_CONTENT[v] || '{}')
              }}
            />
          </Form.Item>
          <Form.Item name="description" label={t('materials.description')}>
            <Input placeholder={t('materials.descriptionPlaceholder')} maxLength={200} />
          </Form.Item>
          <Form.Item
            name="content"
            label={t('materials.contentJson')}
            rules={[{ required: true, message: t('materials.contentJsonRequired') }]}
            initialValue={STARTER_CONTENT.text}
          >
            <TextArea rows={8} style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}

// ---- Main page ----------------------------------------------------------

const MaterialsPage: React.FC = () => {
  const { t } = useTranslation()

  const tabs = [
    {
      key: 'library',
      label: <span><PictureOutlined />{t('materials.tabLibrary')}</span>,
      children: <MaterialList />,
    },
    {
      key: 'generate',
      label: <span><RobotOutlined />{t('materials.tabGenerate')}</span>,
      children: <AIGenerate />,
    },
    {
      key: 'templates',
      label: <span><FileTextOutlined />{t('materials.tabTemplates')}</span>,
      children: <MessageTemplates />,
    },
  ]

  return (
    <div style={{ padding: '16px 24px' }}>
      <Title level={4} style={{ marginBottom: 16 }}>
        <PictureOutlined style={{ marginRight: 8 }} />
        {t('materials.pageTitle')}
      </Title>
      <Tabs items={tabs} destroyInactiveTabPane={false} />
    </div>
  )
}

export default MaterialsPage
