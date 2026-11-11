// サイン波の層: 複数のサイン波を、基準の周波数のまわりに並べて重ね合わせる
// main.scdが読み込み、最後の関数に共通の値と処理を渡してSynthDefを作る。OSCのアドレスはSynthDefの名前になる

// SynthDefの発振器の数は後から変えられないため、サイン波の上限の本数を用意しておく
var maxVoices = 8;
// 隣り合うサイン波の間隔(オクターブ)。狭いとうなりに、広いと別々の高さの音になる
// 狭い間隔ほど少しの違いでうなりの速さが大きく変わるため、対数で対応付ける
var minStepOctaves = 0.0005;
var maxStepOctaves = 1;
// ずれ方のずらし量の上限(段)。隣のサイン波を追い越さないよう、半段までにする
var maxJitterSlots = 0.5;
var jitterOffsets;

// 同じ値からいつも同じ音が出るよう、ずれ方のランダムなずらし量は起動のたびに同じ値にする
thisThread.randSeed = 1;
jitterOffsets = { maxJitterSlots.rand2 } ! maxVoices;

{ |smooth, ampToGain, highFreqGain, minFreq, maxFreq|
	// out以外の値は全て0〜1で受け取る(freqもHzではない)。並びがOSCで送る値の順番になる
	SynthDef(\sines, { |out, freq = 0, count = 0, spread = 0, jitter = 0, amp = 0|
		var baseFreq = smooth.(freq).linexp(0, 1, minFreq, maxFreq);
		var voiceCount = smooth.(count).linlin(0, 1, 1, maxVoices);
		var stepOctaves = smooth.(spread).linexp(0, 1, minStepOctaves, maxStepOctaves);
		var smoothedJitter = smooth.(jitter);
		var volume = ampToGain.(smooth.(amp));
		var voices = maxVoices.collect { |i|
			// 基準の周波数から 0, +1, -1, +2, -2, … 段の位置に並べ、本数を増やすと外側に足されていく
			var slot = (i + 1).div(2) * if(i.odd, 1, -1);
			var position = slot + (jitterOffsets[i] * smoothedJitter);
			var voiceFreq = (baseFreq * (2 ** (position * stepOctaves))).clip(minFreq, maxFreq);
			// 本数の端数の分はその音量で鳴らし、本数の増減がフェードになるようにする
			var voiceAmp = (voiceCount - i).clip(0, 1);
			SinOsc.ar(voiceFreq) * voiceAmp * highFreqGain.(voiceFreq);
		};
		// 本数で割り、全ての波の山が重なっても音量の値を超えないようにする
		Out.ar(out, voices.sum / voiceCount * volume ! 2);
	});
}
