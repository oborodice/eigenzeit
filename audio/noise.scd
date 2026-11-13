// ノイズの層: 全ての周波数を均等に含むホワイトノイズから、帯域を通すフィルタで残す範囲を選んで鳴らす
// main.scdが読み込み、最後の関数に共通の値と処理を渡してSynthDefを作る。OSCのアドレスはSynthDefの名前になる

// 帯域の幅(オクターブ)。狭い側はほぼ1つの音の高さに聴こえる幅、広い側は中心がどこでも聞こえる範囲全体を覆う幅
// 狭い幅ほど少しの違いで聴こえ方が大きく変わるため、対数で対応付ける
var minBandOctaves = 0.01;
var maxBandOctaves = 10;
// WhiteNoiseは-1〜1に均等に散らばるため、実効値は1/√3になる
var whiteNoiseRms = 3.sqrt.reciprocal;

{ |smooth, ampToGain, freqGain, layerRms, minFreq, maxFreq|
	// out以外の値は全て0〜1で受け取る。並びがOSCで送る値の順番になる
	SynthDef(\noise, { |out, center = 0, width = 0, amp = 0|
		var centerFreq = smooth.(center).linexp(0, 1, minFreq, maxFreq);
		var bandOctaves = smooth.(width).linexp(0, 1, minBandOctaves, maxBandOctaves);
		var volume = ampToGain.(smooth.(amp));
		var nyquist = SampleRate.ir / 2;
		// フィルタを通ると、残した帯域の広さに応じて音の量が減る。2次のフィルタは、通す範囲の幅(Hz)のπ/2倍分の音を通す
		// 幅(Hz)は、中心から上下に半分ずつ広げた範囲の、上端と下端の差
		var bandHz = centerFreq * ((2 ** (bandOctaves / 2)) - (2 ** (bandOctaves.neg / 2)));
		var passedHz = (bandHz * 0.5pi).min(nyquist);
		// 幅を変えても音の大きさが揃うよう、どの幅でも他の層と同じ実効値になるように補う
		var gain = (nyquist / passedHz).sqrt * (layerRms / whiteNoiseRms);
		var band = BBandPass.ar(WhiteNoise.ar, centerFreq, bandOctaves) * gain;
		// 広い帯域では高い成分は全体に散らばった一部でしかなく、鋭く高い音にはならないため、高い音かどうかは中心で判断する
		Out.ar(out, band * freqGain.(centerFreq) * volume ! 2);
	});
}
