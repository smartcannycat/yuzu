import type { HttpRequestFn } from '@/api/http/transport'
import type { LotsApi } from '@/api/types'
import type {
  BatchCreateResponse,
  BatchProgressResponse,
  LotListQueryParams,
  LotListResponse,
} from '@/types/api'

function sanitizeLotQuery(
  params?: LotListQueryParams,
): Record<string, string | number | boolean> | undefined {
  if (!params) return undefined

  const cleaned: Record<string, string | number | boolean> = {}
  if (params.query?.trim()) cleaned.query = params.query.trim()
  if (params.make?.trim()) cleaned.make = params.make.trim()
  if (params.model?.trim()) cleaned.model = params.model.trim()
  if (params.verdict) cleaned.verdict = params.verdict
  if (typeof params.has_anomaly === 'boolean') cleaned.has_anomaly = params.has_anomaly
  if (typeof params.page === 'number') cleaned.page = params.page
  if (typeof params.page_size === 'number') cleaned.page_size = params.page_size
  if (params.sort_by) cleaned.sort_by = params.sort_by
  if (params.sort_order) cleaned.sort_order = params.sort_order

  return Object.keys(cleaned).length > 0 ? cleaned : undefined
}

function buildBatchFormData(files: readonly File[]): FormData {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file, file.name)
  }
  return formData
}

export function createHttpLotsApi(request: HttpRequestFn): LotsApi {
  return {
    list(params?: LotListQueryParams): Promise<LotListResponse> {
      return request<LotListResponse>('/lots', {
        method: 'GET',
        query: sanitizeLotQuery(params),
      })
    },

    createBatch(files: readonly File[]): Promise<BatchCreateResponse> {
      return request<BatchCreateResponse>('/lots/batches', {
        method: 'POST',
        body: buildBatchFormData(files),
      })
    },

    getBatch(batchId: string): Promise<BatchProgressResponse> {
      return request<BatchProgressResponse>(`/lots/batches/${encodeURIComponent(batchId)}`, {
        method: 'GET',
      })
    },

    appendBatchItems(batchId: string, files: readonly File[]): Promise<BatchProgressResponse> {
      return request<BatchProgressResponse>(`/lots/batches/${encodeURIComponent(batchId)}/items`, {
        method: 'POST',
        body: buildBatchFormData(files),
      })
    },
  }
}
