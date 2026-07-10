import * as ort from 'onnxruntime-web/webgpu'

export class ONNXEngine {
  private session: ort.InferenceSession | null = null

  async loadModel(modelPath: string): Promise<void> {
    this.session = await ort.InferenceSession.create(modelPath, {
      executionProviders: ['webgpu', 'wasm'],
    })
  }

  async predict(inputTensor: ort.Tensor): Promise<ort.InferenceSession.ReturnType> {
    if (!this.session) throw new Error('Modelo não carregado')
    return this.session.run({ input: inputTensor })
  }

  dispose(): void {
    this.session?.release()
    this.session = null
  }
}
