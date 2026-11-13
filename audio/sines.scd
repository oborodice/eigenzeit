// サイン波の層: 複数のサイン波を、基準の周波数のまわりに並べて重ね合わせ、高さを周期的に揺らす
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
// 高さの揺れの速さ(1秒に揺れる回数)
// 下限は、AIが音を選び直す10秒の間に1回は揺れる回数にし、選んだ値の効果を観測できるようにする(間隔を変えたら見直す)
// 上限は、1秒に10回送るマイクの特徴量が揺れとして追える速さ(送る回数の半分)にする(送る回数を変えたら見直す)
var minWobbleRate = 0.1;
var maxWobbleRate = 5;
// 高さの揺れの深さ(上下それぞれのオクターブ)。下限は高さの違いとして聞き分けられない幅で、ほぼ一定の高さになる
// 上限は広がりの上限に揃え、鳴らして決め直す。狭い深さほど少しの違いで聴こえ方が大きく変わるため、対数で対応付ける
var minWobbleOctaves = 0.001;
var maxWobbleOctaves = 1;

// 同じ値からいつも同じ音が出るよう、ずれ方のランダムなずらし量は起動のたびに同じ値にする
thisThread.randSeed = 1;
jitterOffsets = { maxJitterSlots.rand2 } ! maxVoices;

{ |smooth, ampToGain, freqGain, layerRms, minFreq, maxFreq|
	// out以外の値は全て0〜1で受け取る(freqもHzではない)。並びがOSCで送る値の順番になる
	SynthDef(\sines, { |out, freq = 0, count = 0, spread = 0, jitter = 0, wobbleRate = 0, wobbleDepth = 0, amp = 0|
		var baseFreq = smooth.(freq).linexp(0, 1, minFreq, maxFreq);
		var voiceCount = smooth.(count).linlin(0, 1, 1, maxVoices);
		var stepOctaves = smooth.(spread).linexp(0, 1, minStepOctaves, maxStepOctaves);
		var smoothedJitter = smooth.(jitter);
		var wobbleHz = smooth.(wobbleRate).linexp(0, 1, minWobbleRate, maxWobbleRate);
		var wobbleOctaves = smooth.(wobbleDepth).linexp(0, 1, minWobbleOctaves, maxWobbleOctaves);
		// 全てのサイン波を同じだけ揺らし、広がりで決めた並び方(うなりや音の塊)を保ったまま高さだけを動かす
		// ランダムにふらつかせず周期的に揺らし、同じ値からいつも同じ動きになるようにする
		var wobble = SinOsc.kr(wobbleHz) * wobbleOctaves;
		var volume = ampToGain.(smooth.(amp));
		// 本数の端数の分はその音量で鳴らし、本数の増減がフェードになるようにする
		var voiceAmps = maxVoices.collect { |i| (voiceCount - i).clip(0, 1) };
		// 高さの違うサイン波を重ねた実効値は、振幅の二乗の和の平方根に比例する。本数によらず、合わせた実効値を揃える
		var normalization = layerRms * 2.sqrt / voiceAmps.squared.sum.sqrt;
		var voices = maxVoices.collect { |i|
			// 基準の周波数から 0, +1, -1, +2, -2, … 段の位置に並べ、本数を増やすと外側に足されていく
			var slot = (i + 1).div(2) * if(i.odd, 1, -1);
			var position = slot + (jitterOffsets[i] * smoothedJitter);
			var voiceFreq = (baseFreq * (2 ** ((position * stepOctaves) + wobble))).clip(minFreq, maxFreq);
			SinOsc.ar(voiceFreq) * voiceAmps[i] * freqGain.(voiceFreq);
		};
		Out.ar(out, voices.sum * normalization * volume ! 2);
	});
}
