(
// 値が飛んだときに急に変わらないよう、新しい値へこの時間をかけて一定の速さで移る(AIが音を選び直す間隔と揃える)
var transitionSeconds = 10;
// 下限はHS5が出せる低さ、上限は人間に聞こえる範囲の上限に合わせる。耳は周波数の比で高さを感じるため、対数で対応付ける
// 下限は聴きやすくするための調整ではなく、出せない低さを無理に鳴らしてウーファーを傷めないための制限である
var minFreq = 55;
var maxFreq = 20000;
// SynthDefの発振器の数は後から変えられないため、サイン波の上限の本数を用意しておく
var maxVoices = 8;
// 隣り合うサイン波の間隔(オクターブ)。狭いとうなりに、広いと別々の高さの音になる
// 狭い間隔ほど少しの違いでうなりの速さが大きく変わるため、対数で対応付ける
var minStepOctaves = 0.0005;
var maxStepOctaves = 1;
// 聞こえにくい高い音でも、大きな音量では耳を疲れさせるため、この周波数より上は音量を下げる
// 聴きやすくするための調整ではなく、耳を傷めないための制限であり、人間に合わせて出力を丸めることにはならない
var highFreqStart = 8000;
var highFreqMinGain = 0.25;
// ずれ方のずらし量の上限(段)。隣のサイン波を追い越さないよう、半段までにする
var maxJitterSlots = 0.5;
var jitterOffsets;

// 同じ値からいつも同じ音が出るよう、ずれ方のランダムなずらし量は起動のたびに同じ値にする
thisThread.randSeed = 1;
jitterOffsets = { maxJitterSlots.rand2 } ! maxVoices;

s.waitForBoot {
	var sines;

	// 値は全て0〜1で受け取る(freqもHzではない)
	SynthDef(\sines, { |freq = 0, count = 0, spread = 0, jitter = 0, amp = 0|
		// 0〜1のまま滑らかにしてから実際の値に直し、周波数の高さによって動きの速さが変わって聴こえないようにする
		// lagは指数的に近づき、最初の1秒ほどで大半が動いてしまうため、一定の速さで移るVarLagを使う
		var smooth = { |value| VarLag.kr(value.clip(0, 1), transitionSeconds) };
		var baseFreq = smooth.(freq).linexp(0, 1, minFreq, maxFreq);
		var voiceCount = smooth.(count).linlin(0, 1, 1, maxVoices);
		var stepOctaves = smooth.(spread).linexp(0, 1, minStepOctaves, maxStepOctaves);
		var smoothedJitter = smooth.(jitter);
		var smoothedAmp = smooth.(amp);
		var voices = maxVoices.collect { |i|
			// 基準の周波数から 0, +1, -1, +2, -2, … 段の位置に並べ、本数を増やすと外側に足されていく
			var slot = (i + 1).div(2) * if(i.odd, 1, -1);
			var position = slot + (jitterOffsets[i] * smoothedJitter);
			var voiceFreq = (baseFreq * (2 ** (position * stepOctaves))).clip(minFreq, maxFreq);
			// 本数の端数の分はその音量で鳴らし、本数の増減がフェードになるようにする
			var voiceAmp = (voiceCount - i).clip(0, 1);
			var highFreqGain = voiceFreq.explin(highFreqStart, maxFreq, 1, highFreqMinGain);
			SinOsc.ar(voiceFreq) * voiceAmp * highFreqGain;
		};
		// 本数で割り、全ての波の山が重なっても音量の値を超えないようにする
		Out.ar(0, voices.sum / voiceCount * smoothedAmp ! 2);
	}).add;

	// SynthDefの登録はサーバー側で後から行われるため、終わるのを待ってから鳴らす
	s.sync;

	sines = Synth(\sines);

	OSCdef(\sines, { |msg|
		sines.set(\freq, msg[1], \count, msg[2], \spread, msg[3], \jitter, msg[4], \amp, msg[5]);
	}, '/sines');
};
)
