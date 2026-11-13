// マイクの特徴量: マイクの音から、AIが世界を聴き分けるための値を取り出す
// main.scdが読み込み、返すSynthDefを登録する。値はSynthDefの名前と同じOSCのアドレス(/mic)でsclangに届き、返すtoJsonで名前を付けたJSONにしてPythonへ送る

// ECM999を繋いだMOTU M4の入力(0が入力1)
var inputChannel = 0;
// 1秒に送る回数。うなりのように1秒に数回揺れる大きさの変化も、送った値のばらつきとして捉えられる
var sendRate = 10;
// 部屋の響きを測るときの標準的な細かさである1/3オクターブの帯域(ISO 266)。63Hz〜20kHzの26帯域で、出力の範囲を覆う
var bandOctaves = 1/3;
var bandCenters = (-12..13).collect { |n| 1000 * (10 ** (n / 10)) };
// 完全な無音でdBがマイナス無限大にならないよう止める下限。普段の値は削らないよう、静かな部屋で測った帯域の値より十分低くする
var minDb = -100;
// Onsetsが前提とする長さに合わせる
var fftSize = 512;
// 立ち上がりと数える、音の急な変化の大きさ(Onsetsの既定値)
var onsetThreshold = 0.5;
// sclangに届く値は32ビットの小数で、文字にすると桁が長くなるため、聴き分けに要らない桁を落とす
// dBは、聴いて分かる差よりずっと細かい0.01まで。平坦さは0〜1の値を0.0001刻みまで
var dbStep = 0.01;
var flatnessStep = 0.0001;

var synthDef = SynthDef(\mic, {
	var input = SoundIn.ar(inputChannel);
	var trigger = Impulse.ar(sendRate);
	// 送るたびに0から数え直す値から、0に戻る直前の、送る間隔1回分の値を取り出す
	var beforeReset = { |counter| Latch.ar(Delay1.ar(counter), trigger) };
	// 送る間隔の間に値を足し合わせ、間隔の長さで割って平均にする
	var average = { |signal| beforeReset.(Sweep.ar(trigger, signal)) * sendRate };
	var powerDb = { |signal| average.(signal.squared).max(10 ** (minDb / 10)).log10 * 10 };
	var totalDb = powerDb.(input);
	// 帯域ごとの値は絶対の大きさで表す。全体の大きさとの差にすると、鳴らした帯域が上がっても全体も上がるため、その効果が打ち消されて見えにくくなる
	// FFTは成分が等間隔に並び低い帯域が粗くなるため、帯域ごとのフィルタで測る
	// 1回通すだけでは隣の帯域に7dBほど下がっただけの音が漏れ、帯域を分けた意味が薄れるため、2回通して14dBほど下げる
	var bandDbs = bandCenters.collect { |center|
		var band = BBandPass.ar(BBandPass.ar(input, center, bandOctaves), center, bandOctaves);
		powerDb.(band);
	};
	var chain = FFT(LocalBuf(fftSize), input);
	var flatness = average.(SpecFlatness.kr(chain));
	var onsets = T2A.ar(Onsets.kr(chain, onsetThreshold));
	var onsetCount = beforeReset.(PulseCount.ar(onsets, trigger));
	// triggerは起動した瞬間にも1回鳴るが、そのときはまだ何も足し合わせていないため送らない
	var sendTrigger = trigger * (PulseCount.ar(trigger) > 1);
	SendReply.ar(sendTrigger, '/mic', bandDbs ++ [totalDb, flatness, onsetCount]);
});

// SendReplyの値には名前がないため、並びを決めたこのファイルで名前を付ける
var toJson = { |self, values|
	var bandCount = bandCenters.size;
	var bandDbs = values[0..(bandCount - 1)].collect(_.round(dbStep));
	var totalDb = values[bandCount].round(dbStep);
	var flatness = values[bandCount + 1].round(flatnessStep);
	// SendReplyは数も小数で送るため、整数に直す
	var onsetCount = values[bandCount + 2].asInteger;
	"{\"band_db\": [%], \"total_db\": %, \"flatness\": %, \"onset_count\": %}".format(
		bandDbs.join(", "), totalDb, flatness, onsetCount
	);
};

(synthDef: synthDef, toJson: toJson);
