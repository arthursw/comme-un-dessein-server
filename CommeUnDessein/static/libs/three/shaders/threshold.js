define([], function() {
  return shader = `

varying vec2 vUv;
uniform vec2 resolution;
uniform float threshold;
uniform int windowSize;
uniform sampler2D tDiffuse;

void main()	{

  float t = texture2D(tDiffuse, vUv).x;

  float thresholded = t > threshold ? 1. : 0.;

	gl_FragColor = vec4(thresholded, thresholded, thresholded, 1.);
}`});
