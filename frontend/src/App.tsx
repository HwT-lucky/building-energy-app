import { useState, useCallback } from 'react';
import {
  Steps, Button, Upload, Card, Table, Form, Input, InputNumber, Select,
  Statistic, Alert, Spin, Space, Typography, message, Row, Col, Divider,
  Descriptions, Tag, Tabs, Result, Empty, Badge, Segmented,
} from 'antd';
import {
  FileExcelOutlined, InboxOutlined, DownloadOutlined, ReloadOutlined,
  ExperimentOutlined, ArrowRightOutlined, ArrowLeftOutlined,
  FileTextOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import {
  PieChart, Pie, Cell, ComposedChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, Line, Area, ResponsiveContainer,
} from 'recharts';
import type { UploadFile } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type {
  EnergyMonthRecord, WizardState, MonthlyDataPoint,
} from './types/analysis';
import {
  uploadFile, parseData, matchStandard, fullPipeline, downloadReport, extractErrorMessage,
  previewFile, parseTransposed,
} from './api/client';
import ChatPanel from './components/ChatPanel';
import './App.css';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;

// ============================================================
// Constants
// ============================================================

const BUILDING_TYPES = [
  { value: '办公', label: '办公建筑' },
  { value: '商业', label: '商业建筑（商场/购物中心）' },
  { value: '酒店', label: '旅馆/酒店建筑' },
  { value: '学校', label: '学校建筑（高校/中小学）' },
  { value: '医院', label: '医院建筑' },
  { value: '住宅', label: '居住建筑' },
  { value: '综合', label: '综合建筑' },
];

const PROVINCES = ['北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
  '上海', '江苏', '浙江', '安徽', '福建', '山东', '河南', '湖北', '湖南', '江西',
  '陕西', '甘肃', '青海', '宁夏', '新疆', '广东', '广西', '云南', '贵州', '海南',
  '四川', '重庆', '西藏'];

const STAR_RATINGS = ['五星级', '四星级', '三星级及以下'];

const CLIMATE_ZONES = ['夏热冬冷I区', '夏热冬冷II区', '寒冷地区'];

const CHART_COLORS = {
  electricity: '#f59e0b',
  gas: '#8b5cf6',
  heat: '#ef4444',
  total: '#3b82f6',
  carbon: '#10b981',
};

const STEP_ITEMS = [
  { title: '上传数据' },
  { title: '确认数据' },
  { title: '配置参数' },
  { title: '标准确认' },
  { title: '分析结果' },
];

// ============================================================
// Initial Wizard State
// ============================================================

const initState: WizardState = {
  fileId: null, rawText: null, filename: null,
  parsedData: null, columnMap: null,
  buildingName: '', area: null, buildingType: '', province: '', city: '',
  year: new Date().getFullYear(), starRating: '', climateZone: '',
  matchedStandard: null, confirmedStandard: false,
  coalFactorsPreset: 'national', alpha1: 1.0, alpha2: 1.0, alpha4: 1.0,
  analysisResult: null, carbonResult: null, fullResult: null, isLoading: false,
};

// ============================================================
// Helpers
// ============================================================

function getLevelColor(icon?: string) {
  if (!icon) return 'default';
  if (icon.includes('🟢')) return 'green';
  if (icon.includes('🔵')) return 'blue';
  if (icon.includes('🟡')) return 'gold';
  if (icon.includes('🔴')) return 'red';
  return 'default';
}

function formatNum(n: number | undefined | null, decimals = 0): string {
  if (n == null || isNaN(n)) return '—';
  return n.toLocaleString('zh-CN', { maximumFractionDigits: decimals });
}

// ============================================================
// Main App
// ============================================================

export default function App() {
  const [mode, setMode] = useState<'chat' | 'wizard'>('chat');
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(initState);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [pasteText, setPasteText] = useState('');
  // Parse failure / manual mapping state
  const [parseFailed, setParseFailed] = useState(false);
  const [parseError, setParseError] = useState('');
  const [filePreview, setFilePreview] = useState<Awaited<ReturnType<typeof previewFile>> | null>(null);
  const [showMapping, setShowMapping] = useState(false);
  const [mapElecCol, setMapElecCol] = useState('');
  const [mapGasCol, setMapGasCol] = useState('');
  const [transposedSheet, setTransposedSheet] = useState('');
  const [transposedStartRow, setTransposedStartRow] = useState(2);
  const [transposedMonthCol, setTransposedMonthCol] = useState(2);
  const [transposedNumMonths, setTransposedNumMonths] = useState(12);

  const updateState = useCallback((partial: Partial<WizardState>) => {
    setState(prev => ({ ...prev, ...partial }));
  }, []);

  const resetWizard = () => {
    setStep(0);
    setState(initState);
    setFileList([]);
    setPasteText('');
  };

  // ---- Step 1: Upload & Parse ----
  const handleUpload = async (file: File) => {
    updateState({ isLoading: true });
    try {
      const res = await uploadFile(file);
      updateState({ fileId: res.file_id, filename: res.filename, isLoading: false });
      message.success(`文件 "${res.filename}" 上传成功`);
    } catch (err: unknown) {
      updateState({ isLoading: false });
      const msg = extractErrorMessage(err);
      message.error(`上传失败: ${msg}`);
    }
    return false; // Prevent default upload
  };

  // ---- Step 1: Parse ----
  const handleParse = async () => {
    updateState({ isLoading: true });
    setParseFailed(false); setParseError(''); setShowMapping(false);
    try {
      let result;
      if (state.fileId) {
        result = await parseData({ file_id: state.fileId });
      } else if (pasteText) {
        result = await parseData({ raw_text: pasteText });
      } else {
        message.warning('请先上传文件或粘贴数据');
        updateState({ isLoading: false });
        return;
      }

      // Check if auto-parse failed
      if ((result as unknown as Record<string, unknown>).parse_failed || result.error) {
        const errMsg = result.error || '未能自动识别数据格式';
        setParseFailed(true);
        setParseError(errMsg);
        updateState({ isLoading: false });
        // Auto-fetch preview for Excel files
        if (state.fileId) {
          try {
            const preview = await previewFile(state.fileId);
            setFilePreview(preview);
            // Auto-set transposed params from detection
            const det = preview.detection;
            if (det.mode === 'transposed' && det.confidence > 50) {
              setTransposedSheet(det.sheet || preview.sheets[0]?.name || '');
              setTransposedStartRow(det.data_start_row || 2);
              setTransposedMonthCol(det.month_start_col || 2);
              setTransposedNumMonths(det.num_month_cols || 12);
            }
          } catch { /* preview failed, ignore */ }
        }
        return;
      }

      updateState({
        parsedData: result,
        buildingName: result.building_info?.name || '',
        area: result.building_info?.area || null,
        buildingType: result.building_info?.type || '',
        isLoading: false,
      });
      if (result.warnings?.length) {
        message.warning(`检测到 ${result.warnings.length} 个数据质量问题，请查看详情`);
      }
      setStep(1);
    } catch (err: unknown) {
      updateState({ isLoading: false });
      setParseFailed(true);
      setParseError(extractErrorMessage(err));
      // Try to fetch preview anyway
      if (state.fileId) {
        try { const preview = await previewFile(state.fileId); setFilePreview(preview); } catch { /* ignore */ }
      }
    }
  };

  // ---- Step 1b: Transposed parse ----
  const handleTransposedParse = async () => {
    if (!state.fileId) return;
    updateState({ isLoading: true });
    try {
      const result = await parseTransposed({
        file_id: state.fileId,
        sheet_name: transposedSheet || undefined,
        start_row: transposedStartRow,
        month_start_col: transposedMonthCol,
        num_months: transposedNumMonths,
        year: state.year,
      });
      updateState({
        parsedData: result,
        buildingName: result.building_info?.name || '',
        area: result.building_info?.area || null,
        buildingType: result.building_info?.type || '',
        isLoading: false,
      });
      setParseFailed(false);
      setStep(1);
      const meta = (result as unknown as Record<string, unknown>).meta as Record<string, number> | undefined;
      message.success(`成功按建筑汇总解析！共 ${meta?.rows_aggregated || '?'} 行数据，${transposedNumMonths} 个月`);
    } catch (err: unknown) {
      updateState({ isLoading: false });
      message.error(`转置解析失败: ${extractErrorMessage(err)}`);
    }
  };

  // ---- Step 1c: Manual column mapping parse ----
  const handleManualMapParse = async () => {
    if (!state.fileId) return;
    const cmap: Record<string, string> = {};
    if (mapElecCol) cmap['electricity_kwh'] = mapElecCol;
    if (mapGasCol) cmap['gas_m3'] = mapGasCol;
    if (Object.keys(cmap).length === 0) {
      message.warning('请至少指定一个列映射');
      return;
    }
    updateState({ isLoading: true });
    try {
      const result = await parseData({
        file_id: state.fileId,
        column_map: cmap,
        daily: false,
      });
      if ((result as unknown as Record<string, unknown>).parse_failed || result.error) {
        message.error(result.error || '手动映射后仍未解析到数据');
        updateState({ isLoading: false });
        return;
      }
      updateState({
        parsedData: result,
        buildingName: result.building_info?.name || '',
        area: result.building_info?.area || null,
        buildingType: result.building_info?.type || '',
        isLoading: false,
      });
      setParseFailed(false);
      setStep(1);
    } catch (err: unknown) {
      updateState({ isLoading: false });
      message.error(`映射解析失败: ${extractErrorMessage(err)}`);
    }
  };

  // ---- Step 3: Match Standard ----
  const handleMatchStandard = async () => {
    if (!state.buildingType || !state.province) {
      message.warning('请先选择建筑类型和所在省份');
      return;
    }
    updateState({ isLoading: true });
    try {
      const res = await matchStandard({
        building_type: state.buildingType,
        province: state.province,
        city: state.city,
      });
      if (res.matched && res.standard) {
        updateState({
          matchedStandard: res.standard,
          coalFactorsPreset: res.standard.coal_factors_preset,
          isLoading: false,
        });
        setStep(3);
      } else {
        updateState({ isLoading: false });
        message.warning(res.message || '未找到匹配的标准');
      }
    } catch (err: unknown) {
      updateState({ isLoading: false });
      message.error('标准匹配请求失败');
    }
  };

  // ---- Step 5: Run Full Analysis ----
  const handleRunAnalysis = async () => {
    updateState({ isLoading: true });
    setStep(4);
    try {
      const energyData = state.parsedData?.energy_data || [];
      const hasPreparsed = energyData.length > 0;
      const result = await fullPipeline({
        energy_data: hasPreparsed ? energyData : undefined,
        file_id: hasPreparsed ? undefined : (state.fileId || undefined),
        raw_text: hasPreparsed ? undefined : (state.rawText || undefined),
        building_info: {
          name: state.buildingName,
          area: state.area,
          type: state.buildingType,
          location: `${state.province}${state.city}`,
          year: state.year,
        },
        province: state.province,
        building_type: state.buildingType,
        star_rating: state.starRating || undefined,
        climate_zone: state.climateZone || undefined,
        coal_factors_preset: state.coalFactorsPreset,
      });
      updateState({ fullResult: result, isLoading: false });
      message.success('分析完成！');
    } catch (err: unknown) {
      updateState({ isLoading: false });
      const msg = extractErrorMessage(err);
      message.error(`分析失败: ${msg}`);
    }
  };

  // ---- Report Download ----
  const handleDownloadReport = async () => {
    if (!state.fullResult) return;
    updateState({ isLoading: true });
    try {
      const blob = await downloadReport({
        building_info: { name: state.buildingName, area: state.area, type: state.buildingType, location: `${state.province}${state.city}`, year: state.year },
        energy_proportion: state.fullResult.energy_proportion,
        monthly_trend: state.fullResult.monthly_trend,
        carbon_emission: state.fullResult.carbon_emission,
        standard_comparison: state.fullResult.standard_comparison,
        coal_per_m2_kgce: state.fullResult.coal_per_m2_kgce,
        carbon_intensity_kgco2_per_m2: state.fullResult.carbon_intensity_kgco2_per_m2,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${state.buildingName || '建筑'}_能耗分析报告.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
      updateState({ isLoading: false });
      message.success('报告下载成功！');
    } catch (err: unknown) {
      updateState({ isLoading: false });
      message.error('报告下载失败');
    }
  };

  // ============================================================
  // Render Helpers
  // ============================================================

  const renderStep1 = () => (
    <div className="step-content">
      <Tabs
        defaultActiveKey="upload"
        items={[
          {
            key: 'upload',
            label: <span><FileExcelOutlined /> 文件上传</span>,
            children: (
              <Dragger
                accept=".xlsx,.xls,.csv"
                maxCount={1}
                fileList={fileList}
                onChange={({ fileList: fl }) => setFileList(fl)}
                beforeUpload={handleUpload}
                showUploadList={{ showRemoveIcon: true }}
                className="upload-dragger"
              >
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">点击或拖拽 Excel/CSV 文件到此区域</p>
                <p className="ant-upload-hint">支持 .xlsx、.xls、.csv 格式，最大 20MB</p>
              </Dragger>
            ),
          },
          {
            key: 'paste',
            label: <span><FileTextOutlined /> 粘贴表格</span>,
            children: (
              <TextArea
                rows={10}
                placeholder="在此粘贴 Markdown 表格或纯文本表格数据..."
                value={pasteText}
                onChange={e => setPasteText(e.target.value)}
              />
            ),
          },
          {
            key: 'demo',
            label: <span><ExperimentOutlined /> 示例数据</span>,
            children: (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <Paragraph>使用内置示例数据快速体验分析功能</Paragraph>
                <Button type="primary" onClick={async () => {
                  updateState({ isLoading: true });
                  try {
                    const sampleText = `| 月份 | 用电量(kWh) | 用气量(m³) |
|------|------------|-----------|
| 1 | 450000 | 28000 |
| 2 | 380000 | 25000 |
| 3 | 420000 | 22000 |
| 4 | 470000 | 15000 |
| 5 | 520000 | 8000 |
| 6 | 680000 | 5000 |
| 7 | 750000 | 4000 |
| 8 | 720000 | 4500 |
| 9 | 590000 | 6000 |
| 10 | 480000 | 12000 |
| 11 | 430000 | 20000 |
| 12 | 460000 | 32000 |`;
                    const result = await parseData({ raw_text: sampleText });
                    updateState({
                      parsedData: result,
                      buildingName: '示例商业建筑',
                      area: 30000,
                      buildingType: '商业',
                      isLoading: false,
                    });
                    setPasteText(sampleText);
                    setStep(1);
                  } catch {
                    updateState({ isLoading: false });
                    message.error('示例数据加载失败');
                  }
                }}>加载示例数据</Button>
              </div>
            ),
          },
        ]}
      />
      <div className="step-actions">
        <div></div>
        <Space>
          {state.fileId ? (
            <Button onClick={async () => {
              updateState({ isLoading: true });
              try { const p = await previewFile(state.fileId!); setFilePreview(p); updateState({ isLoading: false }); }
              catch { updateState({ isLoading: false }); }
            }}>🔍 预览文件结构</Button>
          ) : null}
          <Button type="primary" size="large" onClick={handleParse} loading={state.isLoading}
            disabled={!state.fileId && !pasteText}>
            自动解析 <ArrowRightOutlined />
          </Button>
        </Space>
      </div>

      {/* ---- Parse Failure: Show Preview + Mapping Options ---- */}
      {parseFailed ? (
        <div style={{ marginTop: 24 }}>
          <Alert type="warning" showIcon
            message="自动解析失败"
            description={parseError}
            style={{ marginBottom: 16 }}
          />

          {/* Transposed mode suggestion (auto-detected) */}
          {filePreview && filePreview.detection?.mode === 'transposed' && filePreview.detection.confidence > 50 ? (
            <Card size="small" title="📊 检测到「按建筑/子项分行」数据格式"
              style={{ marginBottom: 16, borderColor: '#3b82f6' }}>
              <Alert type="info" showIcon={false}
                message="您的数据格式为：每行=一个建筑，每列=一个月。系统将汇总所有行得到每月总能耗。"
                style={{ marginBottom: 12 }} />
              <Row gutter={[12, 8]}>
                <Col span={8}>
                  <Form.Item label="工作表" labelCol={{ span: 24 }}>
                    <Select value={transposedSheet || undefined}
                      onChange={setTransposedSheet}
                      options={filePreview.sheets.map(s => ({ value: s.name, label: s.name }))} />
                  </Form.Item>
                </Col>
                <Col span={4}><Form.Item label="数据起始行" labelCol={{ span: 24 }}>
                  <InputNumber value={transposedStartRow} onChange={v => setTransposedStartRow(v || 2)} min={1} style={{ width: '100%'}} /></Form.Item></Col>
                <Col span={4}><Form.Item label="月份起始列" labelCol={{ span: 24 }}>
                  <InputNumber value={transposedMonthCol} onChange={v => setTransposedMonthCol(v || 2)} min={1} style={{ width: '100%'}} /></Form.Item></Col>
                <Col span={4}><Form.Item label="月份数" labelCol={{ span: 24 }}>
                  <InputNumber value={transposedNumMonths} onChange={v => setTransposedNumMonths(v || 12)} min={1} max={36} style={{ width: '100%'}} /></Form.Item></Col>
                <Col span={4} style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 4 }}>
                  <Button type="primary" onClick={handleTransposedParse} loading={state.isLoading}
                    style={{ width: '100%' }}>
                    🏢 按建筑汇总解析
                  </Button>
                </Col>
              </Row>
            </Card>
          ) : null}

          {/* Manual Column Mapping */}
          <Card size="small" title="🔧 手动列映射"
            extra={<Button size="small" type="link" onClick={() => setShowMapping(!showMapping)}>
              {showMapping ? '收起' : '展开'}
            </Button>}
            style={{ marginBottom: 16 }}>
            {showMapping ? (
              <>
                <Text type="secondary">如果你的文件是标准格式（每行=一个月），输入电力/燃气对应的 Excel 列号（如 A, B, C...）：</Text>
                <Row gutter={12} style={{ marginTop: 12 }}>
                  <Col span={6}>
                    <Form.Item label="电力列 (如 E)">
                      <Input value={mapElecCol} onChange={e => setMapElecCol(e.target.value.toUpperCase())}
                        placeholder="如: E" maxLength={3} />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="燃气列 (如 G)">
                      <Input value={mapGasCol} onChange={e => setMapGasCol(e.target.value.toUpperCase())}
                        placeholder="如: G" maxLength={3} />
                    </Form.Item>
                  </Col>
                  <Col span={6} style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 4 }}>
                    <Button onClick={handleManualMapParse} loading={state.isLoading}>
                      按映射解析
                    </Button>
                  </Col>
                </Row>
              </>
            ) : (
              <Text type="secondary">点击展开可手动指定电力/燃气对应的列号</Text>
            )}
          </Card>

          {/* File Preview Table */}
          {filePreview ? (
            <Card size="small" title="📋 文件预览">
              {filePreview.sheets.map(sheet => (
                <div key={sheet.name} style={{ marginBottom: 16 }}>
                  <Text strong>{sheet.name}</Text>
                  <Text type="secondary"> ({sheet.total_rows}行 × {sheet.total_cols}列)</Text>
                  <Table
                    dataSource={sheet.preview_rows}
                    rowKey="row"
                    size="small"
                    pagination={false}
                    scroll={{ x: 800 }}
                    style={{ marginTop: 8 }}
                    columns={[
                      { title: '行', dataIndex: 'row', width: 50, fixed: 'left' as const },
                      ...Object.keys(sheet.preview_rows[0]?.cells || {})
                        .slice(0, 20)
                        .map(col => ({
                          title: `列${col}`,
                          dataIndex: ['cells', col] as [string, string],
                          key: col,
                          width: 120,
                          ellipsis: true,
                          render: (_: unknown, record: { cells: Record<string, string> }) => record.cells?.[col] || '',
                        })),
                    ]}
                  />
                </div>
              ))}
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );

  const renderStep2 = () => {
    const data = state.parsedData?.energy_data || [];
    const columns: ColumnsType<EnergyMonthRecord> = [
      { title: '月份', dataIndex: 'month', key: 'month', render: (v: number) => `${v}月` },
      { title: '电力 (kWh)', dataIndex: 'electricity_kwh', key: 'electricity_kwh',
        render: (v: number) => v ? formatNum(v, 0) : '—' },
      { title: '天然气 (m³)', dataIndex: 'gas_m3', key: 'gas_m3',
        render: (v: number) => v ? formatNum(v, 0) : '—' },
      { title: '热力 (GJ)', dataIndex: 'heat_gj', key: 'heat_gj',
        render: (v: number) => v ? formatNum(v, 2) : '—' },
    ];

    return (
      <div className="step-content">
        <Title level={5}>数据预览 ({data.length} 个月)</Title>
        {state.parsedData?.warnings?.length ? (
          <Alert
            type="warning"
            showIcon
            message="数据质量警告"
            description={state.parsedData.warnings.map((w, i) => <div key={i}>• {w.message}</div>)}
            style={{ marginBottom: 16 }}
          />
        ) : null}
        <Table
          dataSource={data}
          columns={columns}
          rowKey="month"
          size="small"
          pagination={false}
          scroll={{ x: 600 }}
          bordered
          summary={() => {
            const totals = data.reduce((acc, r) => ({
              electricity_kwh: acc.electricity_kwh + (r.electricity_kwh || 0),
              gas_m3: acc.gas_m3 + (r.gas_m3 || 0),
              heat_gj: acc.heat_gj + (r.heat_gj || 0),
            }), { electricity_kwh: 0, gas_m3: 0, heat_gj: 0 });
            return (
              <Table.Summary.Row>
                <Table.Summary.Cell index={0}><strong>合计</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={1}><strong>{formatNum(totals.electricity_kwh, 0)}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={2}><strong>{formatNum(totals.gas_m3, 0)}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={3}><strong>{formatNum(totals.heat_gj, 2)}</strong></Table.Summary.Cell>
              </Table.Summary.Row>
            );
          }}
        />
        {state.parsedData?.building_info?.name ? (
          <Descriptions size="small" bordered style={{ marginTop: 16 }} column={3}>
            <Descriptions.Item label="建筑名称">{state.parsedData.building_info.name}</Descriptions.Item>
            <Descriptions.Item label="面积 (m²)">{state.parsedData.building_info.area || '未识别'}</Descriptions.Item>
            <Descriptions.Item label="数据类型">{state.parsedData.data_type || '月度汇总'}</Descriptions.Item>
          </Descriptions>
        ) : null}
        <div className="step-actions">
          <Button onClick={() => setStep(0)}><ArrowLeftOutlined /> 返回</Button>
          <Button type="primary" onClick={() => setStep(2)}>
            下一步：配置参数 <ArrowRightOutlined />
          </Button>
        </div>
      </div>
    );
  };

  const renderStep3 = () => (
    <div className="step-content">
      <Title level={5}>建筑信息配置</Title>
      <Form layout="vertical" style={{ maxWidth: 600 }}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="建筑名称">
              <Input value={state.buildingName} onChange={e => updateState({ buildingName: e.target.value })}
                placeholder="如：XX大厦" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="建筑面积 (m²)" required>
              <InputNumber value={state.area} onChange={v => updateState({ area: v })}
                style={{ width: '100%' }} min={1} placeholder="如：30000" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="建筑类型" required>
              <Select value={state.buildingType || undefined} onChange={v => {
                updateState({ buildingType: v, starRating: '', climateZone: '' });
              }} options={BUILDING_TYPES} placeholder="选择建筑类型" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="所在省份" required>
              <Select value={state.province || undefined} onChange={v => updateState({ province: v })}
                options={PROVINCES.map(p => ({ value: p, label: p }))} placeholder="选择省份"
                showSearch />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item label="城市">
              <Input value={state.city} onChange={e => updateState({ city: e.target.value })}
                placeholder="如：苏州" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="数据年份">
              <InputNumber value={state.year} onChange={v => updateState({ year: v || new Date().getFullYear() })}
                style={{ width: '100%' }} min={2000} max={2100} />
            </Form.Item>
          </Col>
          <Col span={8}>
            {state.buildingType === '酒店' && state.province === '江苏' ? (
              <Form.Item label="星级">
                <Select value={state.starRating || undefined} onChange={v => updateState({ starRating: v })}
                  options={STAR_RATINGS.map(s => ({ value: s, label: s }))} placeholder="选择星级" />
              </Form.Item>
            ) : null}
          </Col>
        </Row>
        {state.buildingType === '酒店' && state.province === '江苏' && state.starRating ? (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="气候分区">
                <Select value={state.climateZone || undefined} onChange={v => updateState({ climateZone: v })}
                  options={CLIMATE_ZONES.map(z => ({ value: z, label: z }))} placeholder="自动检测或手动选择" />
              </Form.Item>
            </Col>
          </Row>
        ) : null}
      </Form>
      <div className="step-actions">
        <Button onClick={() => setStep(1)}><ArrowLeftOutlined /> 返回</Button>
        <Button type="primary" onClick={handleMatchStandard} disabled={!state.buildingType || !state.province || !state.area}>
          自动匹配标准 <ArrowRightOutlined />
        </Button>
      </div>
    </div>
  );

  const renderStep4 = () => {
    const std = state.matchedStandard;
    if (!std) {
      return (
        <div className="step-content">
          <Result status="warning" title="未匹配到适用标准"
            subTitle="请返回上一步确认建筑类型和所在省份" />
          <div className="step-actions">
            <Button onClick={() => setStep(2)}><ArrowLeftOutlined /> 返回配置</Button>
          </div>
        </div>
      );
    }
    return (
      <div className="step-content">
        <Title level={5}>标准确认</Title>
        <Card className="standard-card">
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="标准名称">{std.standard_name}</Descriptions.Item>
            <Descriptions.Item label="标准全称">{std.standard_full}</Descriptions.Item>
            <Descriptions.Item label="电力折算系数">
              {std.coal_electricity} kgce/kWh ({std.is_equivalent_value ? '等价值' : '当量值'})
            </Descriptions.Item>
            <Descriptions.Item label="天然气折算系数">{std.coal_gas} kgce/m³</Descriptions.Item>
            <Descriptions.Item label="电网排放因子">
              {std.grid_factor} kgCO₂/kWh ({std.region})
            </Descriptions.Item>
            <Descriptions.Item label="判定等级">
              <Tag color={std.judgment_levels === 3 ? 'blue' : 'default'}>
                {std.judgment_levels === 3 ? '三级判定（约束值/基准值/引导值）' : '二级判定（约束值/引导值）'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {std.needs_alpha ? (
          <Card title="修正系数（DB31/T 783-2026）" size="small" style={{ marginTop: 16 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item label="α1 设备资产修正" help="<500:0.9 | 500-1000:1.0 | 1000-2000:1.1 | >2000:1.2">
                  <InputNumber value={state.alpha1} onChange={v => updateState({ alpha1: v || 1.0 })}
                    step={0.05} min={0.9} max={2.5} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="α2 学科门类修正" help="艺术:1.05 | 理工:1.3 | 医学:2.0">
                  <InputNumber value={state.alpha2} onChange={v => updateState({ alpha2: v || 1.0 })}
                    step={0.05} min={0.5} max={3.0} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="α4 硕博比修正" help="<30%:1.0 | 30-40%:1.5 | >40%:2.0">
                  <InputNumber value={state.alpha4} onChange={v => updateState({ alpha4: v || 1.0 })}
                    step={0.5} min={0.5} max={3.0} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
          </Card>
        ) : null}

        <Alert
          type="info"
          showIcon
          message="请确认以上标准选择和折算系数是否正确"
          description="确认后将以此标准进行能耗对标分析。如需更换标准，请返回上一步修改建筑类型或省份。"
          style={{ marginTop: 16 }}
        />
        <div className="step-actions">
          <Button onClick={() => setStep(2)}><ArrowLeftOutlined /> 返回修改</Button>
          <Button type="primary" size="large" onClick={handleRunAnalysis} icon={<ThunderboltOutlined />}>
            确认并开始分析
          </Button>
        </div>
      </div>
    );
  };

  const renderStep5 = () => {
    const r = state.fullResult;
    if (!r) {
      return (
        <div className="step-content">
          <Result status="error" title="暂无分析结果" subTitle="请先完成前面的步骤" />
        </div>
      );
    }

    const sc = r.standard_comparison || {};
    const ep = r.energy_proportion || {};
    const mt = r.monthly_trend || {};

    // Pie chart data
    const pieData = (ep.proportions || [])
      .filter((p: { amount: number }) => p.amount > 0)
      .map((p: { label: string; proportion_pct: number }) => ({ name: p.label, value: p.proportion_pct }));

    // Monthly chart data
    const monthlyData: Array<Record<string, unknown>> = (mt.monthly_data || []).map((m: MonthlyDataPoint) => ({
      name: `${m.month}月`,
      '电力(万kWh)': Math.round(m.electricity_kwh / 100) / 10,
      '天然气(万m³)': Math.round(m.gas_m3 / 10) / 100,
      '总能耗(tce)': Math.round(m.total_coal_kgce / 10) / 100,
    }));

    const carbonData: Array<Record<string, unknown>> = (r.carbon_emission?.monthly_emission || []).map(
      (m: { month: number; co2_total: number }) => ({
        name: `${m.month}月`,
        '碳排放(tCO₂)': Math.round(m.co2_total * 100) / 100,
      })
    );

    const pieColors = [CHART_COLORS.electricity, CHART_COLORS.gas, CHART_COLORS.heat];

    return (
      <div className="step-content results-dashboard">
        {/* KPI Cards */}
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Card><Statistic title="年综合能耗" value={formatNum((r.total_coal_kgce || 0) / 1000, 1)} suffix="tce" /></Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card><Statistic title="单位面积能耗"
              value={formatNum(r.coal_per_m2_kgce, 2)} suffix="kgce/m²·a" /></Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card><Statistic title="年碳排放总量"
              value={formatNum(r.carbon_emission?.total_emission_tons, 1)} suffix="tCO₂" /></Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic title="碳排放强度"
                value={formatNum(r.carbon_intensity_kgco2_per_m2, 2)} suffix="kgCO₂/m²·a" />
            </Card>
          </Col>
        </Row>

        {/* Standard Comparison Badge */}
        <Card style={{ marginTop: 16 }}>
          <Space size="large">
            <span style={{ fontSize: 18 }}>{sc.icon} <strong>{sc.level}</strong></span>
            <Tag color={getLevelColor(sc.icon)}>{sc.standard_source}</Tag>
            <Text type="secondary">{sc.message}</Text>
          </Space>
          {sc.energy_message ? <div style={{ marginTop: 8 }}><Text>{sc.energy_message}</Text></div> : null}
          {sc.carbon_message ? <div style={{ marginTop: 4 }}><Text>{sc.carbon_message}</Text></div> : null}
          {sc.suggestion ? <Alert type="info" message={sc.suggestion} style={{ marginTop: 12 }} /> : null}
        </Card>

        {/* Benchmark Table */}
        {sc.status === 'matched' ? (
          <Card title="标准对标详情" size="small" style={{ marginTop: 16 }}>
            <Descriptions bordered size="small" column={3}>
              <Descriptions.Item label="实际单位面积能耗">{formatNum(sc.energy_actual, 2)} kgce/m²·a</Descriptions.Item>
              {sc.energy_constraint != null ? (
                <Descriptions.Item label="约束值">{sc.energy_constraint} kgce/m²·a</Descriptions.Item>
              ) : null}
              {sc.energy_benchmark != null ? (
                <Descriptions.Item label="基准值">{sc.energy_benchmark} kgce/m²·a</Descriptions.Item>
              ) : null}
              {sc.energy_guide != null ? (
                <Descriptions.Item label="引导值">{sc.energy_guide} kgce/m²·a</Descriptions.Item>
              ) : null}
            </Descriptions>
            {sc.carbon_constraint != null ? (
              <>
                <Title level={5} style={{ marginTop: 16 }}>碳排放限额</Title>
                <Descriptions bordered size="small" column={3}>
                  <Descriptions.Item label="实际碳排放强度">{formatNum(sc.carbon_actual, 2)} kgCO₂/m²·a</Descriptions.Item>
                  <Descriptions.Item label="约束值">{sc.carbon_constraint} kgCO₂/m²·a</Descriptions.Item>
                  <Descriptions.Item label="基准值">{sc.carbon_benchmark} kgCO₂/m²·a</Descriptions.Item>
                  <Descriptions.Item label="引导值">{sc.carbon_guide} kgCO₂/m²·a</Descriptions.Item>
                </Descriptions>
              </>
            ) : null}
          </Card>
        ) : null}

        {/* Charts Row */}
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} lg={12}>
            <Card title="能源消耗比例" size="small">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                      outerRadius={100} label={({ name, value }) => `${name} ${value}%`}>
                      {pieData.map((_, i) => <Cell key={i} fill={pieColors[i % pieColors.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : <Empty description="无能源比例数据" />}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title="碳排放结构" size="small">
              {r.carbon_emission?.emission_breakdown ? (
                <div style={{ padding: 24 }}>
                  <Descriptions bordered size="small" column={1}>
                    {r.carbon_emission.emission_breakdown.electricity ? (
                      <Descriptions.Item label="电力">
                        <Badge color={CHART_COLORS.electricity} text={
                          `${formatNum(r.carbon_emission.emission_breakdown.electricity.co2_tons, 1)} tCO₂ (${r.carbon_emission.emission_breakdown.electricity.pct}%)`
                        } />
                      </Descriptions.Item>
                    ) : null}
                    {r.carbon_emission.emission_breakdown.gas ? (
                      <Descriptions.Item label="天然气">
                        <Badge color={CHART_COLORS.gas} text={
                          `${formatNum(r.carbon_emission.emission_breakdown.gas.co2_tons, 1)} tCO₂ (${r.carbon_emission.emission_breakdown.gas.pct}%)`
                        } />
                      </Descriptions.Item>
                    ) : null}
                    {r.carbon_emission.emission_breakdown.heat?.co2_tons > 0 ? (
                      <Descriptions.Item label="热力">
                        <Badge color={CHART_COLORS.heat} text={
                          `${formatNum(r.carbon_emission.emission_breakdown.heat.co2_tons, 1)} tCO₂ (${r.carbon_emission.emission_breakdown.heat.pct}%)`
                        } />
                      </Descriptions.Item>
                    ) : null}
                  </Descriptions>
                  <Divider />
                  <div>电网排放因子: {formatNum(r.carbon_emission.grid_factor_used, 4)} kgCO₂/kWh ({r.carbon_emission.region})</div>
                </div>
              ) : <Empty />}
            </Card>
          </Col>
        </Row>

        {/* Monthly Trend Chart */}
        <Card title="逐月用能走势图" size="small" style={{ marginTop: 16 }}>
          {monthlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={350}>
              <ComposedChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip />
                <Legend />
                <Bar yAxisId="left" dataKey="电力(万kWh)" stackId="a" fill={CHART_COLORS.electricity} name="电力(万kWh)" />
                <Bar yAxisId="left" dataKey="天然气(万m³)" stackId="a" fill={CHART_COLORS.gas} name="天然气(万m³)" />
                <Line yAxisId="right" dataKey="总能耗(tce)" stroke={CHART_COLORS.total}
                  strokeWidth={2} dot={{ r: 4 }} name="总能耗(tce)" />
              </ComposedChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Carbon Trend */}
        <Card title="逐月碳排放趋势" size="small" style={{ marginTop: 16 }}>
          {carbonData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={carbonData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area dataKey="碳排放(tCO₂)" fill={CHART_COLORS.carbon} fillOpacity={0.2}
                  stroke={CHART_COLORS.carbon} strokeWidth={2} />
                <Line dataKey="碳排放(tCO₂)" stroke={CHART_COLORS.carbon} strokeWidth={2}
                  dot={{ r: 5, fill: CHART_COLORS.carbon }} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Monthly Data Table */}
        <Card title="逐月数据明细" size="small" style={{ marginTop: 16 }}>
          <Table
            dataSource={mt.monthly_data || []}
            rowKey="month"
            size="small"
            pagination={false}
            scroll={{ x: 800 }}
            bordered
            columns={[
              { title: '月份', dataIndex: 'month', render: (v: number) => `${v}月` },
              { title: '电力 (kWh)', dataIndex: 'electricity_kwh', render: (v: number) => formatNum(v, 0) },
              { title: '天然气 (m³)', dataIndex: 'gas_m3', render: (v: number) => formatNum(v, 0) },
              { title: '总能耗 (kgce)', dataIndex: 'total_coal_kgce', render: (v: number) => formatNum(v, 0) },
            ]}
            summary={() => (
              <Table.Summary.Row>
                <Table.Summary.Cell index={0}><strong>合计</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={1}><strong>{formatNum((mt.monthly_data || []).reduce((s: number, m: MonthlyDataPoint) => s + (m.electricity_kwh || 0), 0), 0)}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={2}><strong>{formatNum((mt.monthly_data || []).reduce((s: number, m: MonthlyDataPoint) => s + (m.gas_m3 || 0), 0), 0)}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={3}><strong>{formatNum((mt.monthly_data || []).reduce((s: number, m: MonthlyDataPoint) => s + (m.total_coal_kgce || 0), 0), 0)}</strong></Table.Summary.Cell>
              </Table.Summary.Row>
            )}
          />
        </Card>

        {/* Action Buttons */}
        <div className="step-actions" style={{ marginTop: 24 }}>
          <Button onClick={resetWizard} icon={<ReloadOutlined />}>重新分析</Button>
          <Space>
            <Button type="primary" onClick={handleDownloadReport} icon={<DownloadOutlined />}
              loading={state.isLoading} size="large">
              下载 Word 报告 (.docx)
            </Button>
          </Space>
        </div>
      </div>
    );
  };

  // ============================================================
  // Main Render
  // ============================================================

  return (
    <div className="app">
      <header className="app-header">
        <Title level={3} style={{ margin: 0, color: '#fff' }}>
          🏢 建筑能耗分析平台
        </Title>
        <Space style={{ marginTop: 8 }}>
          <Segmented
            value={mode}
            onChange={(v) => setMode(v as 'chat' | 'wizard')}
            options={[
              { value: 'chat', label: '🤖 智能模式', },
              { value: 'wizard', label: '📋 手动模式' },
            ]}
            style={{ background: 'rgba(255,255,255,0.15)' }}
          />
        </Space>
      </header>

      <main className="app-main" style={mode === 'chat' ? { maxWidth: 900 } : undefined}>
        {mode === 'chat' ? (
          <Card className="wizard-card" bodyStyle={{ padding: 0 }}>
            <ChatPanel />
          </Card>
        ) : (
          <Card className="wizard-card">
            <Steps current={step} items={STEP_ITEMS} size="small" style={{ marginBottom: 32 }} />
            <Spin spinning={state.isLoading} tip="处理中...">
              {step === 0 && renderStep1()}
              {step === 1 && renderStep2()}
              {step === 2 && renderStep3()}
              {step === 3 && renderStep4()}
              {step === 4 && renderStep5()}
            </Spin>
          </Card>
        )}
      </main>

      <footer className="app-footer">
        <Text type="secondary">
          数据来源：生态环境部碳排放因子 · GB/T 51161-2016 · 各地方建筑能耗标准
          &nbsp;|&nbsp; 本工具仅供能耗分析参考，不构成法律或政策依据
        </Text>
      </footer>
    </div>
  );
}
