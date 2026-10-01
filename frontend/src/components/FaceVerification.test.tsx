import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FaceVerification } from './FaceVerification';
import { FaceVerificationResult } from '../types';

const matchResult: FaceVerificationResult = {
  similarity: 0.994,
  status: 'MATCH',
  document_face_url: '/uploads/crops/doc.jpg',
  live_face_url: '/uploads/crops/live.jpg',
  quality_checks: {
    mean_brightness: 124.6,
    laplacian_sharpness: 47.0,
    is_blurry: false,
    is_dark: false,
    is_overexposed: false,
  },
  anti_spoofing_score: 0.95,
  match_threshold: 0.72,
};

describe('FaceVerification', () => {
  it('shows an empty state when there is no face result at all', () => {
    render(<FaceVerification />);
    expect(screen.getByText(/No face verification biometric data available/)).toBeInTheDocument();
  });

  it('labels sharpness "Good" when the backend did not flag blur', () => {
    render(<FaceVerification faceResult={matchResult} />);
    expect(screen.getByText(/47 \(Good\)/)).toBeInTheDocument();
  });

  it('labels sharpness "Blurry" when the backend flagged is_blurry -- not a hardcoded "Good"', () => {
    // Reproduces a real bug: the tile previously read "(Good)" for every
    // sharpness value, including ones the Risk Reasons tab simultaneously
    // reported as a FAILED "Live Capture Sharpness" check for motion blur.
    const blurryResult: FaceVerificationResult = {
      ...matchResult,
      quality_checks: { ...matchResult.quality_checks, laplacian_sharpness: 12.0, is_blurry: true },
    };
    render(<FaceVerification faceResult={blurryResult} />);
    expect(screen.getByText(/12 \(Blurry\)/)).toBeInTheDocument();
    expect(screen.queryByText(/12 \(Good\)/)).not.toBeInTheDocument();
  });

  it('shows "Not measured" for sharpness/lighting when face detection failed entirely, not a false "Adequate"/"Balanced"', () => {
    // Reproduces a real bug: NO_FACE_DETECTED/MULTIPLE_FACES results carry
    // no laplacian_sharpness/mean_brightness at all (quality_checks is just
    // {"issue": "..."} or {"multiple_faces_detected": N}) -- the tiles
    // previously defaulted to "Adequate"/"Balanced", falsely implying a
    // passing measurement that never actually ran.
    const noFaceResult: FaceVerificationResult = {
      similarity: 0.0,
      status: 'NO_FACE_DETECTED',
      document_face_url: '/uploads/crops/doc.jpg',
      quality_checks: { issue: 'No face found in live capture' },
      anti_spoofing_score: 0.5,
      match_threshold: 0.72,
    };
    render(<FaceVerification faceResult={noFaceResult} />);
    const notMeasured = screen.getAllByText('Not measured');
    expect(notMeasured.length).toBe(2); // Sharpness tile and Lighting tile
    expect(screen.queryByText('Adequate')).not.toBeInTheDocument();
    expect(screen.queryByText('Balanced')).not.toBeInTheDocument();
  });

  it('a genuine 0.0 sharpness reading is shown as a real measurement, not swallowed into "Not measured"', () => {
    // `quality.laplacian_sharpness != null`, not truthiness -- 0 is a
    // legitimate (if extreme) measured value and is falsy in JS.
    const zeroSharpness: FaceVerificationResult = {
      ...matchResult,
      quality_checks: { ...matchResult.quality_checks, laplacian_sharpness: 0, is_blurry: true },
    };
    render(<FaceVerification faceResult={zeroSharpness} />);
    expect(screen.getByText(/0 \(Blurry\)/)).toBeInTheDocument();
    expect(screen.queryByText('Not measured')).not.toBeInTheDocument();
  });

  it('shows the correct lighting label for an underexposed capture', () => {
    const darkResult: FaceVerificationResult = {
      ...matchResult,
      quality_checks: { ...matchResult.quality_checks, is_dark: true },
    };
    render(<FaceVerification faceResult={darkResult} />);
    expect(screen.getByText('Underexposed')).toBeInTheDocument();
  });
});
