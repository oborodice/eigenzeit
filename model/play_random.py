import random

from pythonosc.udp_client import SimpleUDPClient

from record import Recording, record_while_playing
from sound import AUDIO_ADDRESS, PLAY_SOURCE, random_sound, repeat_every_play_interval, send_sound


def play_random_values(recording: Recording) -> None:
    client = SimpleUDPClient(*AUDIO_ADDRESS)
    rng = random.Random()

    # 好奇心で選んだ場合と比べられるよう、区画を選ばず、どの値も一様な乱数で選ぶ
    def play_once() -> None:
        sound = random_sound(rng)
        send_sound(client, sound)
        recording.write(PLAY_SOURCE, sound)

    repeat_every_play_interval(play_once)


def main() -> None:
    record_while_playing(Recording, play_random_values)


if __name__ == "__main__":
    main()
