import { InferenceService } from './InferenceService';
import { RealInferenceService } from './realInferenceService';
import { MockInferenceService } from '../../mock/mockInferenceService';

// Real mode is the default - set VITE_INFERENCE_MODE=mock to develop against the
// built-in synthetic engine instead (see .env.example).
export const inferenceService: InferenceService =
  import.meta.env.VITE_INFERENCE_MODE === 'mock'
    ? new MockInferenceService()
    : new RealInferenceService();
