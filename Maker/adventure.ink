VAR protagonist_name = "Lady Madeline of Usher"
VAR protagonist_bio = "Survive a terrifying cataleptic state and a premature burial to claw your way back from the tomb for a final, tragic confrontation with your twin."
VAR last_node = "intro"
VAR wealth = 50 // Wealth
VAR health = 50 // Health

-> start_node

=== start_node ===
The adventure begins...
== the_wasting_disease ==
A sense of insufferable gloom pervades the very stones of your ancestral home. You are Lady Madeline, the last daughter of the ancient race of the Ushers. A settled apathy and a gradual wasting away of your person have long baffled your physicians. As you glide silently through the remote, shadowy portions of the vast, tattered apartments, you feel the oppressive weight of the mansion pressing upon your chest. Through the open archway of your brother Roderick's studio, you glimpse a stranger—Roderick's childhood friend, summoned to alleviate his madness. Your brother's face is buried in his hands, his luminous eyes wild with despair.
# IMAGE: the_wasting_disease_main.png
* [Pass slowly through the remote portion of the apartment, ignoring the stranger to preserve your rapidly fading strength.] -> the_wasting_disease_result_1
* [Pause by the ancient, sombre tapestries, drawing a strange, dark vitality from the very decay of the house itself.] -> the_wasting_disease_result_2
* [Attempt to call out to the stranger, hoping to warn him of the pestilent and mystic vapour that enshrouds the domain.] -> the_wasting_disease_result_3



~ last_node = "the_wasting_disease"
== the_wasting_disease_result_1 ==
You drift through the shadows without acknowledging the guest. The effort is minimal, allowing you to retreat to your chambers with a shred of vitality remaining. You leave behind an atmosphere of profound dread.
~ health = health + 10
-> the_wasting_disease_next

== the_wasting_disease_result_2 ==
You press your pale hand against the cold, fungus-covered stone. A morbid energy, born of the sentient arrangement of the Usher estate, flows into your veins. You feel momentarily fortified by the curse that binds your family.
# IMAGE: the_wasting_disease_reward.png
# good
~ health = health + 15
~ wealth = wealth - 5
-> the_wasting_disease_next

== the_wasting_disease_result_3 ==
You open your lips, but only a dry, rattling gasp escapes. The exertion triggers a violent spasm in your chest. Your vision swims, and you are forced to flee into the darkness, utterly exhausted.
# bad
-> the_wasting_disease


== the_wasting_disease_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in the_wasting_disease_next...]
-> END


== the_cataleptical_trance ==
On the closing in of the evening, the prostrating power of the destroyer finally overcomes you. You lie in your bedchamber, surrounded by dark draperies that sway fitfully. The transient affections of your partially cataleptical character suddenly deepen into a terrifying abyss. Your limbs grow heavy, your breath shallows to an imperceptible whisper, and your eyes fix upon the vaulted ceiling. You are entirely paralyzed, locked in the mockery of a faint blush upon your bosom and face, wearing that suspiciously lingering smile upon the lip which is so terrible in death. You are aware, but you cannot move.
# IMAGE: the_cataleptical_trance_main.png
* [Surrender your mind to the silent void, conserving your inner spark for the inevitable awakening.] -> the_cataleptical_trance_result_1
* [Retreat into the deep, ancestral memories of the Usher bloodline, finding a hidden reserve of supernatural willpower.] -> the_cataleptical_trance_result_2
* [Fight the paralysis with inner panic, screaming endlessly within the confines of your frozen skull.] -> the_cataleptical_trance_result_3



~ last_node = "the_cataleptical_trance"
== the_cataleptical_trance_result_1 ==
You let the darkness wash over your consciousness. By not fighting the paralysis, you preserve the fragile ember of life deep within your chest, waiting patiently for the spell to break.
~ health = health + 10
-> the_cataleptical_trance_next

== the_cataleptical_trance_result_2 ==
Your mind delves into the centuries of Usher history. You commune with the phantoms of your lineage, forging an unbreakable mental fortitude that defies the boundaries of mortality.
# IMAGE: the_cataleptical_trance_reward.png
# good
~ health = health + 5
~ wealth = wealth + 15
-> the_cataleptical_trance_next

== the_cataleptical_trance_result_3 ==
Your mind thrashes in terror against its fleshy prison. The silent panic burns through your rapidly fading oxygen, leaving your spirit weakened and your body closer to true death.
# bad
-> the_cataleptical_trance


== the_cataleptical_trance_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in the_cataleptical_trance_next...]
-> END


== the_mournful_burden ==
Footsteps approach. It is Roderick, accompanied by his friend. Through the haze of your rigid trance, you feel yourself being lifted and placed into a wooden box. You hear Roderick's tremulous, hollow-sounding enunciation as he speaks of your unusual malady and his intention to preserve your corpse for a fortnight within the main walls of the building. You are entirely helpless as they carry you down, down, through the dark and intricate passages of the mansion, toward the deep vaults.
# IMAGE: the_mournful_burden_main.png
* [Focus entirely on slowing your heart rate further, ensuring your mind survives the absolute deprivation of air.] -> the_mournful_burden_result_1
* [Listen closely to their footsteps and the echoes of the walls, memorizing the path to the upper house.] -> the_mournful_burden_result_2
* [Attempt to force a single tear from your eye to show them you are alive.] -> the_mournful_burden_result_3



~ last_node = "the_mournful_burden"
== the_mournful_burden_result_1 ==
You sink into a state of profound hibernation. Your need for oxygen drops to a mere fraction of a breath, protecting your brain from the suffocating enclosure of the coffin.
~ health = health + 10
-> the_mournful_burden_next

== the_mournful_burden_result_2 ==
You map the descent in your mind: the long corridors, the sharp turns, the descent beneath the narrator's sleeping apartment. You forge a mental key to your eventual escape.
# IMAGE: the_mournful_burden_reward.png
# good
~ health = health + 5
~ wealth = wealth + 10
-> the_mournful_burden_next

== the_mournful_burden_result_3 ==
You strain with all your might, but the cataleptic lock holds firm. The immense effort only exhausts your trapped mind, leaving you drained as the descent continues.
# bad
-> the_mournful_burden


== the_mournful_burden_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in the_mournful_burden_next...]
-> END


== the_copper_vault ==
You are brought into a region of horror—a small, damp vault entirely without means of admission for light, lying at a great depth. It was once a donjon-keep, its floor and archway sheathed with copper. You feel the coffin set upon tressels. Roderick and his friend look upon your face one last time. You hear Roderick murmur about the sympathies of a scarcely intelligible nature that existed between you two as twins. Then, the lid is replaced. The screws are turned. The massive iron door grates sharply upon its hinges, sealing you in absolute, oppressive darkness.
# IMAGE: the_copper_vault_main.png
* [Embrace the silence. Wait patiently for the disease's natural cycle to release you from its grip.] -> the_copper_vault_result_1
* [Draw upon the cursed sentience of the Usher stones around you, forging a dark, symbiotic bond with the vault itself.] -> the_copper_vault_result_2
* [Let the unimaginable terror of being buried alive consume your thoughts.] -> the_copper_vault_result_3



~ last_node = "the_copper_vault"
== the_copper_vault_result_1 ==
You float in the dark, timeless void. Days pass, but your conserved energy sustains you. You wait for the exact moment the paralysis begins to thaw.
~ health = health + 10
-> the_copper_vault_next

== the_copper_vault_result_2 ==
The copper sheathing and the gray stones hum with a terrible, importunate influence. You absorb this dark energy, binding your life force to the very foundations of the House of Usher.
# IMAGE: the_copper_vault_reward.png
# good
~ health = health + 15
~ wealth = wealth - 5
-> the_copper_vault_next

== the_copper_vault_result_3 ==
The grim phantasm of FEAR overtakes you. The crushing weight of the earth above seems to press directly onto your chest. Your mind fractures under the strain of the absolute darkness.
# bad
-> the_copper_vault


== the_copper_vault_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in the_copper_vault_next...]
-> END


== awakening_in_the_coffin ==
Seven or eight days pass. Suddenly, the icy grip of the catalepsy shatters. You draw a ragged, desperate breath of stale air. You are awake. You are alive. And you are entombed. The pitch-black confinement of the screwed-down coffin presses against your face and shoulders. Panic rises like a rapid, ghastly river. You must escape before the suffocating atmosphere claims you forever.
# IMAGE: awakening_in_the_coffin_main.png
* [Use measured, deliberate force to press against the wood, finding the weakest point in the unscrewed lid.] -> awakening_in_the_coffin_result_1
* [Channel the supernatural fury of your ancestors, tearing through the wood with unnatural, terrifying strength.] -> awakening_in_the_coffin_result_2
* [Thrash wildly in the dark, bruising your limbs and tearing your fingernails to shreds in a blind panic.] -> awakening_in_the_coffin_result_3



~ last_node = "awakening_in_the_coffin"
== awakening_in_the_coffin_result_1 ==
You suppress your panic. Feeling along the edges, you find a section where the wood is dry and hollow-sounding. With a concentrated heave, you crack the planking, allowing the damp air of the vault to rush in.
~ health = health + 10
-> awakening_in_the_coffin_next

== awakening_in_the_coffin_result_2 ==
A mad hilarity and superhuman energy fill your limbs. You strike the lid with the force of a demon, ripping and tearing the wood asunder. The noise reverberates throughout the vault like the breaking of a hermit's door.
# IMAGE: awakening_in_the_coffin_reward.png
# good
~ health = health + 5
~ wealth = wealth - 10
-> awakening_in_the_coffin_next

== awakening_in_the_coffin_result_3 ==
You scream and claw aimlessly at the hard wood. Your fingers bleed profusely, and your strength wanes rapidly. Only by sheer, desperate luck does a rusty screw give way, but you are severely injured.
# bad
-> awakening_in_the_coffin


== awakening_in_the_coffin_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in awakening_in_the_coffin_next...]
-> END


== the_iron_door ==
You tumble from the ruined coffin onto the copper floor. But your prison is not yet breached. Before you stands the door of massive iron, its immense weight protecting the archway. Your white robes are stained with blood, your frame emaciated from the long starvation. You hear the faint, muffled sounds of a rising tempest outside, but here, deep in the earth, you are alone with the impenetrable iron.
# IMAGE: the_iron_door_main.png
* [Use a broken piece of wood from the tressels as a lever to pry the heavy hinges open.] -> the_iron_door_result_1
* [Throw your emaciated body against the door, letting your blood and fury act as a dark sacrifice to open the way.] -> the_iron_door_result_2
* [Claw fruitlessly at the solid iron, weeping in despair as you lose precious blood and time.] -> the_iron_door_result_3



~ last_node = "the_iron_door"
== the_iron_door_result_1 ==
Applying leverage rather than raw strength, you force the wood into the gap. With a harsh, protracted, and unusual grating sound, the immense iron door slowly yields, saving your torn hands from further ruin.
~ health = health + 10
-> the_iron_door_next

== the_iron_door_result_2 ==
You slam against the iron. The impact is agonizing, but the sentient house responds to the spilled blood of its final daughter. The door swings open with a mighty, clangorous reverberation, as if a brazen shield had fallen upon a silver floor.
# IMAGE: the_iron_door_reward.png
# good
~ health = health - 5
~ wealth = wealth + 15
-> the_iron_door_next

== the_iron_door_result_3 ==
You tear your already ruined hands against the unyielding metal. Only after agonizing hours of pushing do you manage to shift the heavy hinges just enough to squeeze your bruised body through.
# bad
-> the_iron_door


== the_iron_door_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in the_iron_door_next...]
-> END


== ascent_through_the_storm ==
You have escaped the donjon. You drag yourself up the dark, intricate staircases. A fierce tempest is raging, the wind howling through the old mansion. The exceeding density of the clouds hangs low, glowing in the unnatural light of a faintly luminous gaseous exhalation. As you near Roderick's chamber, you hear the heavy, horrible beating of your own heart. From within the room, you hear Roderick's shrieking voice: 'Madman! I tell you that she now stands without the door!'
# IMAGE: ascent_through_the_storm_main.png
* [Time your heavy, dragging footsteps with the thunder, building a terrifying momentum for your entrance.] -> ascent_through_the_storm_result_1
* [Let the storm's electrical miasma infuse your spirit, transforming you into an avenging wraith of the Usher line.] -> ascent_through_the_storm_result_2
* [Stumble and fall on the jagged stone steps, your heart giving out as you drag yourself upward.] -> ascent_through_the_storm_result_3



~ last_node = "ascent_through_the_storm"
== ascent_through_the_storm_result_1 ==
You move with the rhythm of the storm. Each step is a declaration of your return from the grave. You gather the last remnants of your mortal strength, preparing to confront the brother who buried you prematurely.
~ health = health + 10
-> ascent_through_the_storm_next

== ascent_through_the_storm_result_2 ==
The unnatural, leaden-hued vapour wraps around you. You are no longer merely Lady Madeline; you are the physical manifestation of the House's doom, glowing with a ghastly, inappropriate splendour.
# IMAGE: ascent_through_the_storm_reward.png
# good
~ health = health + 15
~ wealth = wealth + 5
-> ascent_through_the_storm_next

== ascent_through_the_storm_result_3 ==
Your knees buckle. You drag your broken body up the final steps, leaving a trail of blood. Your heart is beating so violently it threatens to burst from your chest before you even reach the door.
# bad
-> ascent_through_the_storm


== ascent_through_the_storm_next ==
// TEMPORARY PLACEHOLDER
[...The story continues in ascent_through_the_storm_next...]
-> END


== the_final_embrace ==
You stand before the huge antique panels of Roderick's chamber. As if in the superhuman energy of his utterance there had been found the potency of a spell, the ponderous and ebony jaws of the door are thrown slowly back by the rushing gust. You stand there—the lofty and enshrouded figure of the lady Madeline of Usher. There is blood upon your white robes, and the evidence of some bitter struggle upon every portion of your emaciated frame. Roderick stares at you, paralyzed by the grim phantasm of his own fear.
# IMAGE: the_final_embrace_main.png
-> END



~ last_node = "the_final_embrace"
