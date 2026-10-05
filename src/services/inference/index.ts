import { InferenceService } from './InferenceService';
import { RealInferenceService } from './realInferenceService';
import { MockInferenceService } from '../../mock/mockInferenceService';

export const inferenceService: InferenceService =
  import.meta.env.VITE_INFERENCE_MODE === 'real'
    ? new RealInferenceService()
    : new MockInferenceService();
